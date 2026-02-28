import os
import time
import logging
from typing import Optional, Any, Dict

import psycopg2
import threading
from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool

logger = logging.getLogger("mcp.db")


class DBConnection:
    """Database connection manager using a threaded connection pool.

    Reads configuration from environment variables. Supports either a
    `DATABASE_URL` (full DSN) or individual `POSTGRES_*` vars.

    Usage:
        db = DBConnection()
        conn = db.get_conn()
        cur = conn.cursor()
        ...
        db.put_conn(conn)
        db.close_all()
    """

    def __init__(
        self,
        minconn: int = 1,
        maxconn: int = 5,
        retries: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        self.minconn = minconn
        self.maxconn = maxconn
        # Shared pool across instances to avoid creating many pools
        self._pool: Optional[SimpleConnectionPool] = None
        # ensure class-level helpers exist
        if not hasattr(DBConnection, "_global_pool"):
            DBConnection._global_pool = None
        if not hasattr(DBConnection, "_pool_lock"):
            DBConnection._pool_lock = threading.Lock()
        if not hasattr(DBConnection, "_reuse_logged"):
            DBConnection._reuse_logged = False

        # Fast path: if global pool exists, reuse it (no locking)
        if DBConnection._global_pool:
            self._pool = DBConnection._global_pool
            # log reuse only once to avoid spamming logs
            if not DBConnection._reuse_logged:
                logger.info("Reusing existing DB connection pool")
                DBConnection._reuse_logged = True
            return

        # Build connection parameters
        database_url = os.getenv("DATABASE_URL")
        conn_kwargs: Dict[str, Any] = {}

        if database_url:
            conn_kwargs["dsn"] = database_url
        else:
            dbname = os.getenv("POSTGRES_DB")
            user = os.getenv("POSTGRES_USER")
            password = os.getenv("POSTGRES_PASSWORD")
            host = os.getenv("POSTGRES_HOST", "localhost")
            port = os.getenv("POSTGRES_PORT", "5432")
            sslmode = os.getenv("POSTGRES_SSLMODE")

            missing = []
            if not dbname:
                missing.append("POSTGRES_DB")
            if not user:
                missing.append("POSTGRES_USER")
            if not password:
                missing.append("POSTGRES_PASSWORD")
            if missing:
                raise ValueError(f"Missing required DB environment variables: {', '.join(missing)}")

            conn_kwargs = {
                "dbname": dbname,
                "user": user,
                "password": password,
                "host": host,
                "port": port,
            }
            if sslmode:
                conn_kwargs["sslmode"] = sslmode

        # Allow override of max connections via env var
        try:
            env_max = int(os.getenv("POSTGRES_MAX_CONN", "0"))
            if env_max > 0:
                self.maxconn = env_max
        except Exception:
            pass

        # Attempt to create a SimpleConnectionPool with retries
        # Use a lock to avoid multiple threads creating multiple pools concurrently
        with DBConnection._pool_lock:
            # another thread may have created the pool while we waited
            if DBConnection._global_pool:
                self._pool = DBConnection._global_pool
                if not DBConnection._reuse_logged:
                    logger.info("Reusing existing DB connection pool")
                    DBConnection._reuse_logged = True
                return
        attempt = 0
        while attempt < retries:
            try:
                if "dsn" in conn_kwargs:
                    # Create a SimpleConnectionPool using a DSN string
                    self._pool = SimpleConnectionPool(self.minconn, self.maxconn, dsn=conn_kwargs["dsn"])
                else:
                    # Create a SimpleConnectionPool using explicit connection parameters
                    self._pool = SimpleConnectionPool(self.minconn, self.maxconn, **conn_kwargs)
                logger.info("DB connection pool created")
                # store global pool for reuse
                DBConnection._global_pool = self._pool
                DBConnection._reuse_logged = True
                break
            except OperationalError as e:
                attempt += 1
                logger.warning(f"DB connection attempt {attempt} failed: {e}")
                if attempt >= retries:
                    logger.error("Exceeded max retries while connecting to DB")
                    raise
                time.sleep(retry_delay)

    def get_conn(self):
        if not self._pool:
            raise RuntimeError("Connection pool is not initialized")
        return self._pool.getconn()

    def put_conn(self, conn) -> None:
        if self._pool and conn is not None:
            try:
                self._pool.putconn(conn)
            except Exception:
                logger.exception("Failed to return connection to pool")

    def close_all(self) -> None:
        if self._pool:
            try:
                self._pool.closeall()
                logger.info("Closed all DB connections")
            except Exception:
                logger.exception("Error closing DB pool")

    def execute_query(self, query: str, params: Optional[tuple] = None, fetch: bool = True):
        """Convenience method to execute a query using a pooled connection.

        Returns fetched rows (list of dicts) when `fetch` is True, otherwise
        returns number of affected rows.
        """
        conn = None
        cur = None
        rows = None
        affected = None
        try:
            conn = self.get_conn()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Helper: replace the nth occurrence of a substring
            def _replace_nth(s: str, old: str, n: int, new: str) -> str:
                pos = -1
                start = 0
                for i in range(n + 1):
                    pos = s.find(old, start)
                    if pos == -1:
                        return s
                    start = pos + len(old)
                return s[:pos] + new + s[pos + len(old):]

            # Expand positional query placeholders for a sequence element at the given index
            def _expand_positional_query(q: str, seq_indexes: Dict[int, int]) -> str:
                # seq_indexes: mapping param_index -> sequence_length
                # we must replace occurrences from left to right; find %s occurrences
                parts = q.split("%s")
                if len(parts) - 1 < max(seq_indexes.keys(), default=-1) + 1:
                    # not enough placeholders; return original
                    return q
                out = []
                for i, part in enumerate(parts[:-1]):
                    out.append(part)
                    if i in seq_indexes:
                        l = seq_indexes[i]
                        if l <= 0:
                            raise ValueError("Cannot expand empty sequence for SQL parameter")
                        out.append("(" + ",".join(["%s"] * l) + ")")
                    else:
                        out.append("%s")
                out.append(parts[-1])
                return "".join(out)

            # Expand named params like %(name)s when the value is a sequence
            def _expand_named_query(q: str, seq_keys_lengths: Dict[str, int]) -> str:
                for key, l in seq_keys_lengths.items():
                    if l <= 0:
                        raise ValueError("Cannot expand empty sequence for SQL parameter")
                    placeholder = "%(" + key + ")s"
                    new_placeholders = ",".join([f"%({key}_{i})s" for i in range(l)])
                    q = q.replace(placeholder, "(" + new_placeholders + ")")
                return q

            # Support multiple parameter styles:
            # - None -> no params
            # - dict -> named params (%(name)s)
            # - tuple/list -> single param set
            # - list of tuples/dicts -> multiple param sets -> executemany
            if params is None:
                normalized = ()

                logger.debug("Executing query without params: %s", query)
                cur.execute(query, normalized)
                if fetch:
                    rows = cur.fetchall()
                else:
                    affected = cur.rowcount
                    conn.commit()

            elif isinstance(params, dict):
                # detect any dict values that are sequences and expand named placeholders
                seq_keys_lengths: Dict[str, int] = {}
                new_params: Dict[str, Any] = {}
                for k, v in params.items():
                    if isinstance(v, (list, tuple)):
                        seq_keys_lengths[k] = len(v)
                        for i, item in enumerate(v):
                            new_params[f"{k}_{i}"] = item
                    else:
                        new_params[k] = v

                if seq_keys_lengths:
                    q = _expand_named_query(query, seq_keys_lengths)
                    logger.debug("Expanded named query: %s", q)
                    cur.execute(q, new_params)
                else:
                    logger.debug("Executing query with named params: %s | %s", query, params)
                    cur.execute(query, params)
                if fetch:
                    rows = cur.fetchall()
                else:
                    affected = cur.rowcount
                    conn.commit()

            elif isinstance(params, list) and params and isinstance(params[0], (list, tuple, dict)):
                # Multiple parameter sets -> executemany
                logger.debug("Detected multiple parameter sets; using executemany() | %s sets", len(params))
                first = params[0]
                # positional param sets (list/tuple)
                if isinstance(first, (list, tuple)):
                    seq_indexes: Dict[int, int] = {}
                    for idx, val in enumerate(first):
                        if isinstance(val, (list, tuple)):
                            seq_indexes[idx] = len(val)
                    if seq_indexes:
                        q = _expand_positional_query(query, seq_indexes)
                        logger.debug("Expanded positional query for executemany: %s", q)
                        # flatten all param sets according to seq_indexes
                        flattened_sets = []
                        for pset in params:
                            flat = []
                            for i, v in enumerate(pset):
                                if i in seq_indexes:
                                    flat.extend(list(v))
                                else:
                                    flat.append(v)
                            flattened_sets.append(tuple(flat))
                        cur.executemany(q, flattened_sets)
                    else:
                        cur.executemany(query, params)

                # named param sets (dict)
                else:
                    # detect keys that are sequences
                    seq_keys_lengths: Dict[str, int] = {}
                    for k, v in first.items():
                        if isinstance(v, (list, tuple)):
                            seq_keys_lengths[k] = len(v)
                    if seq_keys_lengths:
                        q = _expand_named_query(query, seq_keys_lengths)
                        logger.debug("Expanded named query for executemany: %s", q)
                        new_param_sets = []
                        for pset in params:
                            newp = {}
                            for k, v in pset.items():
                                if k in seq_keys_lengths:
                                    for i, item in enumerate(v):
                                        newp[f"{k}_{i}"] = item
                                else:
                                    newp[k] = v
                            new_param_sets.append(newp)
                        cur.executemany(q, new_param_sets)
                    else:
                        cur.executemany(query, params)

                if fetch:
                    raise ValueError("Cannot fetch results when executing multiple parameter sets (executemany)")
                affected = cur.rowcount
                conn.commit()

            else:
                # single tuple/list or scalar
                if isinstance(params, (list, tuple)):
                    normalized = tuple(params)
                else:
                    normalized = (params,)

                logger.debug("Executing query: %s | params type: %s", query, type(normalized))
                cur.execute(query, normalized)
                if fetch:
                    rows = cur.fetchall()
                else:
                    affected = cur.rowcount
                    conn.commit()

        except Exception:
            logger.exception("Error executing query")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            if cur:
                try:
                    cur.close()
                except Exception:
                    pass
            if conn:
                try:
                    self.put_conn(conn)
                except Exception:
                    pass

        return rows if fetch else affected

