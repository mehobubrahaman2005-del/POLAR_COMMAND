// ==========================================
// POLAR COMMAND - OFFLINE SYSTEM
// Connection Status + IndexedDB + Sync
// ==========================================


// ==========================================
// 1. ONLINE / OFFLINE STATUS
// ==========================================

function updateConnectionStatus() {

    const online = navigator.onLine;

    let indicator =
        document.getElementById("connection-status");

    if (!indicator) {

        indicator = document.createElement("div");

        indicator.id = "connection-status";

        // Same position on every page
        indicator.style.position = "fixed";
        indicator.style.top = "10px";
        indicator.style.right = "10px";
        indicator.style.zIndex = "99999";
        indicator.style.padding = "9px 16px";
        indicator.style.borderRadius = "22px";
        indicator.style.fontSize = "14px";
        indicator.style.fontWeight = "600";
        indicator.style.boxShadow =
            "0 2px 8px rgba(0,0,0,0.12)";

        document.body.appendChild(indicator);
    }


    if (online) {

        indicator.innerHTML = "🟢 Online";

        indicator.style.background = "#d4edda";
        indicator.style.color = "#155724";

    } else {

        indicator.innerHTML = "🟠 Offline Mode";

        indicator.style.background = "#fff3cd";
        indicator.style.color = "#856404";
    }
}


// ==========================================
// INTERNET LOST
// ==========================================

window.addEventListener("offline", () => {

    updateConnectionStatus();

    console.log(
        "POLAR COMMAND: Offline Mode activated."
    );

});


// ==========================================
// INTERNET RESTORED
// ==========================================

window.addEventListener("online", async () => {

    updateConnectionStatus();

    console.log(
        "POLAR COMMAND: Internet connection restored."
    );

    console.log(
        "POLAR COMMAND: Starting sync..."
    );

    /*
     * IMPORTANT:
     * First upload pending offline changes.
     * Then download latest server data.
     */

    await syncPendingChanges();

    await syncServerDataToLocal();

});


// ==========================================
// INITIAL STATUS
// ==========================================

document.addEventListener(
    "DOMContentLoaded",
    () => {

        updateConnectionStatus();

    }
);

// ==========================================
// 2. POLAR COMMAND INDEXEDDB
// ==========================================

const DB_NAME = "POLAR_COMMAND_DB";

const DB_VERSION = 3;


// ==========================================
// DATABASE STORES
// ==========================================

const STORES = [

    "stations",

    "inventory",

    "cargo",

    "personnel",

    "equipment",

    "emergencies",

    "tasks",

    "decisions",

    "resource_usage",

    "pending_sync",

    "conflicts"

];



// ==========================================
// 3. OPEN DATABASE
// ==========================================

function openPolarDatabase() {

    return new Promise(
        (resolve, reject) => {

            const request =
                indexedDB.open(
                    DB_NAME,
                    DB_VERSION
                );


            request.onupgradeneeded =
                function(event) {

                    const db =
                        event.target.result;


                    STORES.forEach(
                        storeName => {

                            if (
                                !db.objectStoreNames
                                    .contains(storeName)
                            ) {

                                db.createObjectStore(
                                    storeName,
                                    {
                                        keyPath: "id",
                                        autoIncrement: true
                                    }
                                );

                            }

                        }
                    );


                    console.log(
                        "POLAR COMMAND: IndexedDB stores checked/created."
                    );

                };


            request.onsuccess =
                function(event) {

                    const db =
                        event.target.result;


                    console.log(
                        "POLAR COMMAND: Local database opened."
                    );


                    resolve(db);

                };


            request.onerror =
                function(event) {

                    console.error(
                        "POLAR COMMAND: IndexedDB error:",
                        event.target.error
                    );


                    reject(
                        event.target.error
                    );

                };

        }
    );

}



// ==========================================
// 4. INITIALIZE LOCAL DATABASE
// ==========================================

document.addEventListener(
    "DOMContentLoaded",
    async () => {

        try {

            const db =
                await openPolarDatabase();


            console.log(
                "POLAR COMMAND: Local database ready:",
                db.name
            );


            db.close();

        }

        catch (error) {

            console.error(
                "POLAR COMMAND: Local database initialization failed:",
                error
            );

        }

    }
);



// ==========================================
// 5. SERVER → LOCAL INDEXEDDB SYNC
// ==========================================

async function syncServerDataToLocal() {

    if (!navigator.onLine) {

        console.log(
            "POLAR COMMAND: Offline. Server sync skipped."
        );

        return;

    }


    try {

        console.log(
            "POLAR COMMAND: Downloading server data..."
        );


        const response =
            await fetch(
                "/api/offline-data",
                {
                    method: "GET",
                    cache: "no-store"
                }
            );


        if (!response.ok) {

            throw new Error(
                "Server returned " +
                response.status
            );

        }


        const data =
            await response.json();


        if (data.error) {

            throw new Error(
                data.error
            );

        }


        const db =
            await openPolarDatabase();


        const availableStores =
            Object.keys(data)
                .filter(
                    storeName =>
                        db.objectStoreNames
                            .contains(storeName)
                );


        if (
            availableStores.length === 0
        ) {

            db.close();

            return;

        }


        const transaction =
            db.transaction(
                availableStores,
                "readwrite"
            );


        availableStores.forEach(
            storeName => {

                const store =
                    transaction.objectStore(
                        storeName
                    );


                const records =
                    data[storeName];


                if (
                    !Array.isArray(records)
                ) {

                    return;

                }


                records.forEach(
                    record => {

                        store.put(record);

                    }
                );

            }
        );


        transaction.oncomplete =
            function() {

                console.log(
                    "POLAR COMMAND: Server data saved to IndexedDB."
                );


                db.close();

            };


        transaction.onerror =
            function(event) {

                console.error(
                    "POLAR COMMAND: IndexedDB server sync error:",
                    event.target.error
                );


                db.close();

            };

    }

    catch (error) {

        console.error(
            "POLAR COMMAND: Server data sync failed:",
            error
        );

    }

}



// ==========================================
// 6. OFFLINE CRUD ENGINE
// ==========================================

async function saveOfflineRecord(
    storeName,
    record,
    action = "UPDATE"
) {

    try {

        const db =
            await openPolarDatabase();


        const transaction =
            db.transaction(
                [
                    storeName,
                    "pending_sync"
                ],
                "readwrite"
            );


        const store =
            transaction.objectStore(
                storeName
            );


        const syncStore =
            transaction.objectStore(
                "pending_sync"
            );


        // ==================================
        // CREATE
        // ==================================

        if (
            action === "CREATE" &&
            !record.id
        ) {

            const addRequest =
                store.add(record);


            addRequest.onsuccess =
                function() {

                    const localId =
                        addRequest.result;


                    syncStore.add({

                        store:
                            storeName,

                        action:
                            "CREATE",

                        record_id:
                            localId,

                        local_id:
                            localId,

                        data: {
                            ...record,
                            id: localId
                        },

                        created_at:
                            new Date()
                                .toISOString(),

                        synced:
                            false

                    });

                };

        }


        // ==================================
        // UPDATE
        // ==================================

        else {

            store.put(record);


            syncStore.add({

                store:
                    storeName,

                action:
                    action,

                record_id:
                    record.id || null,

                local_id:
                    record.id || null,

                data:
                    record,

                created_at:
                    new Date()
                        .toISOString(),

                synced:
                    false

            });

        }


        transaction.oncomplete =
            function() {

                console.log(
                    "POLAR COMMAND: Offline record queued:",
                    storeName,
                    action
                );


                db.close();

            };


        transaction.onerror =
            function(event) {

                console.error(
                    "POLAR COMMAND: Offline queue error:",
                    event.target.error
                );


                db.close();

            };

    }

    catch (error) {

        console.error(
            "POLAR COMMAND: Offline CRUD error:",
            error
        );

    }

}



// ==========================================
// 7. OFFLINE UPDATE INVENTORY
// ==========================================

async function updateOfflineInventory(
    id,
    itemName,
    station,
    quantity,
    minimumQuantity,
    dailyConsumption,
    unit,
    riskLevel,
    baseQuantity
) {

    try {

        /*
         * IMPORTANT:
         *
         * The ORIGINAL quantity must be captured
         * BEFORE the offline modification.
         *
         * We therefore read the existing IndexedDB
         * inventory record first.
         */

        const db =
            await openPolarDatabase();


        const readTransaction =
            db.transaction(
                "inventory",
                "readonly"
            );


        const inventoryStore =
            readTransaction.objectStore(
                "inventory"
            );


        const existingRecord =
            await new Promise(
                (resolve, reject) => {

                    const request =
                        inventoryStore.get(
                            Number(id)
                        );


                    request.onsuccess =
                        function() {

                            resolve(
                                request.result || null
                            );

                        };


                    request.onerror =
                        function() {

                            reject(
                                request.error
                            );

                        };

                }
            );


        /*
         * Determine ORIGINAL quantity.
         *
         * Priority:
         *
         * 1. Existing base_quantity
         *    (important for repeated offline edits)
         *
         * 2. Existing quantity
         *    (first offline edit)
         *
         * 3. Supplied baseQuantity
         *
         * 4. Current quantity
         */

        let originalQuantity = null;


        if (
            existingRecord &&
            Number.isFinite(
                Number(
                    existingRecord.base_quantity
                )
            )
        ) {

            originalQuantity =
                Number(
                    existingRecord.base_quantity
                );

        }


        else if (
            existingRecord &&
            Number.isFinite(
                Number(
                    existingRecord.quantity
                )
            )
        ) {

            originalQuantity =
                Number(
                    existingRecord.quantity
                );

        }


        else if (
            Number.isFinite(
                Number(baseQuantity)
            )
        ) {

            originalQuantity =
                Number(baseQuantity);

        }


        else {

            originalQuantity =
                Number(quantity);

        }


        /*
         * IMPORTANT SAFETY CHECK:
         *
         * If the supplied baseQuantity is exactly
         * the NEW quantity, do NOT use it as the
         * original quantity when an existing record
         * is available.
         */

        if (
            existingRecord &&
            Number.isFinite(
                Number(existingRecord.quantity)
            ) &&
            Number(existingRecord.quantity) !==
                Number(quantity) &&
            Number(existingRecord.base_quantity) ===
                Number(existingRecord.quantity)
        ) {

            originalQuantity =
                Number(existingRecord.quantity);

        }


        const record = {

            id:
                Number(id),

            item_name:
                itemName,

            station:
                station,

            quantity:
                Number(quantity),

            minimum_quantity:
                Number(minimumQuantity),

            daily_consumption:
                Number(dailyConsumption),

            unit:
                unit,

            risk_level:
                riskLevel,

            /*
             * THIS IS THE IMPORTANT FIX.
             *
             * Store the ORIGINAL quantity,
             * not the newly edited quantity.
             */

            base_quantity:
                originalQuantity

        };


        db.close();


        await saveOfflineRecord(
            "inventory",
            record,
            "UPDATE"
        );


        console.log(
            "POLAR COMMAND: Inventory updated in Offline Mode:",
            record
        );


        console.log(
            "POLAR COMMAND: Original Base Quantity:",
            originalQuantity
        );

    }

    catch (error) {

        console.error(
            "POLAR COMMAND: Offline inventory update failed:",
            error
        );

    }

}



// ==========================================
// 8. OFFLINE ADD INVENTORY
// ==========================================

async function addOfflineInventory(
    itemName,
    station,
    quantity,
    minimumQuantity,
    dailyConsumption,
    unit,
    riskLevel
) {

    const record = {

        item_name:
            itemName,

        station:
            station,

        quantity:
            Number(quantity),

        minimum_quantity:
            Number(minimumQuantity),

        daily_consumption:
            Number(dailyConsumption),

        unit:
            unit,

        risk_level:
            riskLevel

    };


    await saveOfflineRecord(
        "inventory",
        record,
        "CREATE"
    );


    console.log(
        "POLAR COMMAND: Inventory added in Offline Mode:",
        record
    );

}



// ==========================================
// 9. OFFLINE DELETE INVENTORY
// ==========================================

async function deleteOfflineInventory(id) {

    try {

        const db =
            await openPolarDatabase();


        const transaction =
            db.transaction(
                [
                    "inventory",
                    "pending_sync"
                ],
                "readwrite"
            );


        const inventoryStore =
            transaction.objectStore(
                "inventory"
            );


        const syncStore =
            transaction.objectStore(
                "pending_sync"
            );


        inventoryStore.delete(
            Number(id)
        );


        syncStore.add({

            store:
                "inventory",

            action:
                "DELETE",

            record_id:
                Number(id),

            local_id:
                Number(id),

            data: {

                id:
                    Number(id)

            },

            created_at:
                new Date()
                    .toISOString(),

            synced:
                false

        });


        transaction.oncomplete =
            function() {

                console.log(
                    "POLAR COMMAND: Inventory deleted in Offline Mode:",
                    id
                );


                db.close();

            };


        transaction.onerror =
            function(event) {

                console.error(
                    "POLAR COMMAND: Offline delete error:",
                    event.target.error
                );


                db.close();

            };

    }

    catch (error) {

        console.error(
            "POLAR COMMAND: Offline inventory delete failed:",
            error
        );

    }

}



// ==========================================
// 10. GET PENDING SYNC RECORDS
// ==========================================

async function getPendingSyncRecords() {

    return new Promise(
        async function(resolve, reject) {

            try {

                const db =
                    await openPolarDatabase();


                const transaction =
                    db.transaction(
                        "pending_sync",
                        "readonly"
                    );


                const store =
                    transaction.objectStore(
                        "pending_sync"
                    );


                const request =
                    store.getAll();


                request.onsuccess =
                    function() {

                        const records =
                            request.result
                                .filter(
                                    item =>
                                        item.synced !== true
                                );


                        resolve(
                            records
                        );


                        db.close();

                    };


                request.onerror =
                    function() {

                        reject(
                            request.error
                        );


                        db.close();

                    };

            }

            catch (error) {

                reject(
                    error
                );

            }

        }
    );

}



// ==========================================
// 11. SEND ONE RECORD TO SERVER
// ==========================================

async function sendSyncRecord(
    syncRecord
) {

    try {

        const response =
            await fetch(
                "/api/sync",
                {
                    method: "POST",

                    headers: {

                        "Content-Type":
                            "application/json"

                    },

                    body:
                        JSON.stringify({

                            store:
                                syncRecord.store,

                            action:
                                syncRecord.action,

                            local_id:
                                syncRecord.local_id ||
                                syncRecord.record_id ||
                                null,

                            data:
                                syncRecord.data

                        })

                }
            );


        const result =
            await response.json();


        if (!response.ok) {

            return {

                success:
                    false,

                conflict:
                    result.conflict ||
                    false,

                conflict_type:
                    result.conflict_type ||
                    null,

                local_record:
                    result.local_record ||
                    syncRecord.data ||
                    null,

                server_record:
                    result.server_record ||
                    null,

                message:
                    result.message ||
                    "Sync failed"

            };

        }


        return {

            ...result,

            success:
                result.success !== false

        };

    }

    catch (error) {

        console.error(
            "POLAR COMMAND: Sync request failed:",
            error
        );


        return {

            success:
                false,

            networkError:
                true

        };

    }

}



// ==========================================
// 12. REMOVE SYNC QUEUE ITEM
// ==========================================

function removeSyncQueueItem(id) {

    return new Promise(
        async function(resolve, reject) {

            try {

                const db =
                    await openPolarDatabase();


                const transaction =
                    db.transaction(
                        "pending_sync",
                        "readwrite"
                    );


                const store =
                    transaction.objectStore(
                        "pending_sync"
                    );


                store.delete(id);


                transaction.oncomplete =
                    function() {

                        db.close();

                        resolve(
                            true
                        );

                    };


                transaction.onerror =
                    function() {

                        db.close();

                        reject(
                            transaction.error
                        );

                    };

            }

            catch (error) {

                reject(
                    error
                );

            }

        }
    );

}



// ==========================================
// 13. MAIN SYNC FUNCTION
// ==========================================

async function syncPendingChanges() {

    if (!navigator.onLine) {

        console.log(
            "POLAR COMMAND: Offline. Sync skipped."
        );

        return;

    }


    console.log(
        "POLAR COMMAND: Starting pending sync..."
    );


    try {

        const pending =
            await getPendingSyncRecords();


        if (
            pending.length === 0
        ) {

            console.log(
                "POLAR COMMAND: No pending changes."
            );

            return;

        }


        console.log(
            "POLAR COMMAND:",
            pending.length,
            "pending changes found."
        );


        for (
            const syncRecord
            of pending
        ) {

            const result =
                await sendSyncRecord(
                    syncRecord
                );


            // ==================================
            // SUCCESS
            // ==================================

            if (
                result.success
            ) {

                await removeSyncQueueItem(
                    syncRecord.id
                );


                // ==================================
                // CREATE → SERVER ID
                // ==================================

                if (
                    syncRecord.action ===
                        "CREATE" &&
                    result.server_id
                ) {

                    await replaceLocalInventoryId(
                        syncRecord,
                        result.server_id
                    );

                }


                console.log(
                    "POLAR COMMAND: Sync successful:",
                    syncRecord.action
                );

            }


            // ==================================
            // CONFLICT
            // ==================================

            else if (
                result.conflict
            ) {

                console.warn(
                    "POLAR COMMAND: Conflict detected.",
                    result
                );


                await saveConflict({

                    conflict_type:
                        result.conflict_type,

                    local_record:
                        result.local_record ||
                        syncRecord.data,

                    server_record:
                        result.server_record ||
                        null,

                    sync_queue_id:
                        syncRecord.id

                });


                /*
                 * Remove conflicted queue item
                 * so it does not create the same
                 * conflict repeatedly.
                 */

                await removeSyncQueueItem(
                    syncRecord.id
                );


                console.warn(
                    "POLAR COMMAND: Conflict saved for resolution."
                );

            }


            // ==================================
            // NETWORK ERROR
            // ==================================

            else if (
                result.networkError
            ) {

                console.warn(
                    "POLAR COMMAND: Network error. Sync will retry later."
                );

            }


            // ==================================
            // OTHER SYNC ERROR
            // ==================================

            else {

                console.warn(
                    "POLAR COMMAND: Sync failed:",
                    syncRecord,
                    result
                );

            }

        }


        console.log(
            "POLAR COMMAND: Sync process completed."
        );

    }

    catch (error) {

        console.error(
            "POLAR COMMAND Sync Engine Error:",
            error
        );

    }

}



// ==========================================
// 14. REPLACE LOCAL ID AFTER SERVER CREATE
// ==========================================

async function replaceLocalInventoryId(
    syncRecord,
    serverId
) {

    try {

        const db =
            await openPolarDatabase();


        const transaction =
            db.transaction(
                "inventory",
                "readwrite"
            );


        const store =
            transaction.objectStore(
                "inventory"
            );


        const localId =
            Number(
                syncRecord.local_id ||
                syncRecord.record_id
            );


        const request =
            store.get(
                localId
            );


        request.onsuccess =
            function() {

                const record =
                    request.result;


                if (!record) {

                    return;

                }


                store.delete(
                    localId
                );


                record.id =
                    Number(serverId);


                store.put(
                    record
                );

            };


        transaction.oncomplete =
            function() {

                console.log(
                    "POLAR COMMAND: Local ID replaced with server ID:",
                    serverId
                );


                db.close();

            };


        transaction.onerror =
            function(event) {

                console.error(
                    "POLAR COMMAND: Local ID replacement failed:",
                    event.target.error
                );


                db.close();

            };

    }

    catch (error) {

        console.error(
            "POLAR COMMAND: ID replacement error:",
            error
        );

    }

}



// ==========================================
// 15. SAVE CONFLICT LOCALLY
// ==========================================

async function saveConflict(
    conflictData
) {

    return new Promise(
        async function(resolve, reject) {

            try {

                const db =
                    await openPolarDatabase();


                const transaction =
                    db.transaction(
                        "conflicts",
                        "readwrite"
                    );


                const store =
                    transaction.objectStore(
                        "conflicts"
                    );


                const request =
                    store.add({

                        store:
                            "inventory",

                        conflict_type:
                            conflictData.conflict_type ||
                            "UNKNOWN",

                        local_record:
                            conflictData.local_record ||
                            null,

                        server_record:
                            conflictData.server_record ||
                            null,

                        sync_queue_id:
                            conflictData.sync_queue_id ||
                            null,

                        created_at:
                            new Date()
                                .toISOString(),

                        resolved:
                            false

                    });


                request.onsuccess =
                    function() {

                        console.warn(
                            "POLAR COMMAND: Conflict saved locally."
                        );

                    };


                transaction.oncomplete =
                    function() {

                        db.close();

                        resolve(
                            true
                        );

                    };


                transaction.onerror =
                    function(event) {

                        console.error(
                            "POLAR COMMAND: Conflict storage error:",
                            event.target.error
                        );


                        db.close();

                        reject(
                            event.target.error
                        );

                    };

            }

            catch (error) {

                console.error(
                    "POLAR COMMAND: Save conflict failed:",
                    error
                );


                reject(
                    error
                );

            }

        }
    );

}



// ==========================================
// 16. STARTUP SYNC
// ==========================================

async function startPolarSync() {

    if (!navigator.onLine) {

        console.log(
            "POLAR COMMAND: Startup sync skipped - Offline."
        );

        return;

    }


    console.log(
        "POLAR COMMAND: Startup sync started..."
    );


    /*
     * IMPORTANT ORDER:
     *
     * 1. Upload pending local changes
     * 2. Download latest server data
     */

    await syncPendingChanges();

    await syncServerDataToLocal();


    console.log(
        "POLAR COMMAND: Startup sync completed."
    );

}



// ==========================================
// 17. RUN STARTUP SYNC
// ==========================================

document.addEventListener(
    "DOMContentLoaded",
    () => {

        setTimeout(
            () => {

                startPolarSync();

            },
            1000
        );

    }
);