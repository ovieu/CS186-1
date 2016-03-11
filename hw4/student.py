import logging

from kvstore import DBMStore, InMemoryKVStore

LOG_LEVEL = logging.WARNING

KVSTORE_CLASS = InMemoryKVStore

"""
Possible abort modes.
"""
USER = 0
DEADLOCK = 1

"""
Part I: Implementing request handling methods for the transaction handler

The transaction handler has access to the following objects:

self._lock_table: the global lock table. More information in the README.

self._acquired_locks: a list of locks acquired by the transaction. Used to
release locks when the transaction commits or aborts. This list is initially
empty.

self._desired_lock: the lock that the transaction is waiting to acquire as well
as the operation to perform. This is initialized to None.

self._xid: this transaction's ID. You may assume each transaction is assigned a
unique transaction ID.

self._store: the in-memory key-value store. You may refer to kvstore.py for
methods supported by the store.

self._undo_log: a list of undo operations to be performed when the transaction
is aborted. The undo operation is a tuple of the form (@key, @value). This list
is initially empty.

You may assume that the key/value inputs to these methods are already type-
checked and are valid.
"""

class TransactionHandler:

    def __init__(self, lock_table, xid, store):
        # Lock table, value = list of tuples (xid, lock type)
        self._lock_table = lock_table
        self._acquired_locks = []
        self._desired_lock = None
        self._xid = xid
        self._store = store
        self._undo_log = []

        self._queue_table = {} # Added, myself.

    def perform_put(self, key, value):
        """
        Handles the PUT request. You should first implement the logic for
        acquiring the exclusive lock. If the transaction can successfully
        acquire the lock associated with the key, insert the key-value pair
        into the store.

        Hint: if the lock table does not contain the key entry yet, you should
        create one.
        Hint: be aware that lock upgrade may happen.
        Hint: remember to update self._undo_log so that we can undo all the
        changes if the transaction later gets aborted. See the code in abort()
        for the exact format.

        @param self: the transaction handler.
        @param key, value: the key-value pair to be inserted into the store.

        @return: if the transaction successfully acquires the lock and performs
        the insertion/update, returns 'Success'. If the transaction cannot
        acquire the lock, returns None, and saves the lock that the transaction
        is waiting to acquire in self._desired_lock.
        """
        # Part 1.1: your code here!

	    # Acquire exclusive lock (includes if you already have the X lock).
        if not self.acquire_Xlock(key):
            self._desired_lock = (self._xid, "X")
            return None
	 

	    # If got lock, can insert pair into store.

        self._store.put(key, value)

        # Update undo log
        self._undo_log.append((key, value))
        
        return 'Success'


    def acquire_Xlock(self, key):
        """
        Acquires exclusive lock, if possible. 

        @param self: the transaction handler
        @param key: key to acquire lock for
        @return: True if Xlock acquired. False if not. 
        """
        # If already have lock, done.
        own_lock = self.has_lock(key)
        if own_lock is not None and own_lock[1] == "X":
            return True

        # If no one locking it, OR you're the only one locking it, just get it. 
        if key not in self._lock_table:
            self._lock_table[key] = [(self._xid, "X")]
            self._acquired_locks.append((self._xid, "X"))
            return True  

        lt_entry = self._lock_table[key] # List 
        if len(lt_entry) == 1 and lt_entry[0][0] == self._xid:
            lt_entry = [(self._xid, "X")]
            self.upgrade_lock(key)
            return True 
	     
        
        curr_queue = []
        if key in self._queue_table:
            curr_queue = self._queue_table[key]

        # If you want to upgrade, but other shares, cut queue.
        if len(lt_entry) > 1 and own_lock is not None and own_lock[1] == "S":
            self._queue_table[key] = [(self._xid, "X")] + curr_queue
            return False

        # Else, just get in the queue.
        self._queue_table[key] = curr_queue + [(self._xid, "X")]
        return False

    def has_lock(self, key):
        """
        Returns lock, if has it.

        @return: lock, if has it. None if does not. 
        
        """
        for i in range(len(self._acquired_locks)):
            if self._acquired_locks[i][0] == key:
                return self._acquired_locks[i]
        return None


    def upgrade_lock(self, key):
        """ 
        Updates self._acquired_locks, from "S" to "X"

        """
        for i in range(len(self._acquired_locks)):
            if self._acquired_locks[i][0] == key and self._acquired_locks[i][1] == "S":
                self._acquired_locks[i][1] == "X"
                return 

    def perform_get(self, key):
        """ 
        Handles the GET request. You should first implement the logic for
        acquiring the shared lock. If the transaction can successfully acquire
        the lock associated with the key, read the value from the store.

        Hint: if the lock table does not contain the key entry yet, you should
        create one.

        @param self: the transaction handler.
        @param key: the key to look up from the store.

        @return: if the transaction successfully acquires the lock and reads
        the value, returns the value. If the key does not exist, returns 'No
        such key'. If the transaction cannot acquire the lock, returns None,
        and saves the lock that the transaction is waiting to acquire in
        self._desired_lock.
        """
        # Part 1.1: your code here!
        
        
        # Acquire shared lock

        # If doesn't work, put in desired lock!!!! 
        
        value = self._store.get(key)
        if value is None:
            return 'No such key'

        # Acquire shared lock

        if not self.acquire_Slock(key):
            self._desired_lock = (self._xid, "S")
            return None
        
        else:
            return value


    def acquire_Slock(self, key):
        """
        Acquires shared lock, if possible. 

        @return: True if Slock acquired. False if not. 

        """
        # If already have lock, done
        own_lock = self.has_lock(key)
        if own_lock is not None and own_lock[1] == "S":
            return True

        # No downgrades allowed! 

        # If no one locking it, good.
        if key not in self._lock_table:
            self._lock_table[key] = [(self._xid, "S")]
            self._acquired_locks.append((self._xid, "S"))
            return True

        # If someone has an exclusive lock on it, off. 

        curr_queue = []
        if key in self._queue_table:
            curr_queue = self._queue_table[key]
        if self.exists_Xlock(key):
            # Put self in queue
            self._queue_table[key] = curr_queue.append((self._xid, "S"))
            return False
        

        # Else, everyone on it has a shared lock; join in.
        self._lock_table[key] = self._lock_table[key].append((self._xid, "S"))
        self._acquired_locks_append((self._xid, "S"))
        return True
        

    def exists_Xlock(self, key):
        lock_list = self._lock_table[key]
        for i in range(len(lock_list)):
            if lock_list[i][1] == "X":
                return True

        return False

    

    def release_and_grant_locks(self):
        """
        Releases all locks acquired by the transaction and grants them to the
        next transactions in the queue. This is a helper method that is called
        during transaction commits or aborts. 

        Hint: you can use self._acquired_locks to get a list of locks acquired
        by the transaction.
        Hint: be aware that lock upgrade may happen.

        @param self: the transaction handler.
        """
        for l in self._acquired_locks:
            pass # Part 1.2: your code here!
        self._acquired_locks = []

    def commit(self):
        """
        Commits the transaction.

        Note: This method is already implemented for you, and you only need to
        implement the subroutine release_locks().

        @param self: the transaction handler.

        @return: returns 'Transaction Completed'
        """
        self.release_and_grant_locks()
        return 'Transaction Completed'

    def abort(self, mode):
        """
        Aborts the transaction.

        Note: This method is already implemented for you, and you only need to
        implement the subroutine release_locks().

        @param self: the transaction handler.
        @param mode: mode can either be USER or DEADLOCK. If mode == USER, then
        it means that the abort is issued by the transaction itself (user
        abort). If mode == DEADLOCK, then it means that the transaction is
        aborted by the coordinator due to deadlock (deadlock abort).

        @return: if mode == USER, returns 'User Abort'. If mode == DEADLOCK,
        returns 'Deadlock Abort'.
        """
        while (len(self._undo_log) > 0):
            k,v = self._undo_log.pop()
            self._store.put(k, v)
        self.release_and_grant_locks()
        if (mode == USER):
            return 'User Abort'
        else:
            return 'Deadlock Abort'

    def check_lock(self):
        """
        If perform_get() or perform_put() returns None, then the transaction is
        waiting to acquire a lock. This method is called periodically to check
        if the lock has been granted due to commit or abort of other
        transactions. If so, then this method returns the string that would 
        have been returned by perform_get() or perform_put() if the method had
        not been blocked. Otherwise, this method returns None.

        As an example, suppose Joe is trying to perform 'GET a'. If Nisha has an
        exclusive lock on key 'a', then Joe's transaction is blocked, and
        perform_get() returns None. Joe's server handler starts calling
        check_lock(), which keeps returning None. While this is happening, Joe
        waits patiently for the server to return a response. Eventually, Nisha
        decides to commit his transaction, releasing his exclusive lock on 'a'.
        Now, when Joe's server handler calls check_lock(), the transaction
        checks to make sure that the lock has been acquired and returns the
        value of 'a'. The server handler then sends the value back to Joe.

        Hint: self._desired_lock contains the lock that the transaction is
        waiting to acquire.
        Hint: remember to update the self._acquired_locks list if the lock has
        been granted.
        Hint: if the transaction has been granted an exclusive lock due to lock
        upgrade, remember to clean up the self._acquired_locks list.
        Hint: remember to update self._undo_log so that we can undo all the
        changes if the transaction later gets aborted.

        @param self: the transaction handler.

        @return: if the lock has been granted, then returns whatever would be
        returned by perform_get() and perform_put() when the transaction
        successfully acquired the lock. If the lock has not been granted,
        returns None.
        """
        pass # Part 1.3: your code here!







"""
Part II: Implement deadlock detection method for the transaction coordinator

The transaction coordinator has access to the following object:

self._lock_table: see description from Part I
"""

class TransactionCoordinator:

    def __init__(self, lock_table):
        self._lock_table = lock_table

    def detect_deadlocks(self):
        """
        Constructs a waits-for graph from the lock table, and runs a cycle
        detection algorithm to determine if a transaction needs to be aborted.
        You may choose which one transaction you plan to abort, as long as your
        choice is deterministic. For example, if transactions 1 and 2 form a
        cycle, you cannot return transaction 1 sometimes and transaction 2 the
        other times.

        This method is called periodically to check if any operations of any
        two transactions conflict. If this is true, the transactions are in
        deadlock - neither can proceed. If there are multiple cycles of
        deadlocked transactions, then this method will be called multiple
        times, with each call breaking one of the cycles, until it returns None
        to indicate that there are no more cycles. Afterward, the surviving
        transactions will continue to run as normal.

        Note: in this method, you only need to find and return the xid of a
        transaction that needs to be aborted. You do not have to perform the
        actual abort.

        @param self: the transaction coordinator.

        @return: If there are no cycles in the waits-for graph, returns None.
        Otherwise, returns the xid of a transaction in a cycle.
        """
        pass # Part 2.1: your code here!