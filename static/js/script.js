// ========================================== 
// POLAR COMMAND - SERVICE WORKER REGISTRATION 
// ========================================== 
 
if ("serviceWorker" in navigator) { 
 
    window.addEventListener("load", () => { 
 
        navigator.serviceWorker.register("/service-worker.js") 
 
            .then(registration => { 
 
                console.log( 
                    "POLAR COMMAND Service Worker registered:", 
                    registration.scope 
                ); 
 
                // ========================================== 
                // BACKGROUND SYNC REGISTRATION 
                // ========================================== 
 
                if ("SyncManager" in window) { 
 
                    registration.sync.register( 
                        "polar-pending-sync" 
                    ) 
 
                    .then(() => { 
 
                        console.log( 
                            "POLAR COMMAND: Background Sync registered." 
                        ); 
 
                    }) 
 
                    .catch(error => { 
 
                        console.error( 
                            "POLAR COMMAND: Background Sync registration failed:", 
                            error 
                        ); 
 
                    }); 
 
                } else { 
 
                    console.log( 
                        "POLAR COMMAND: Background Sync not supported." 
                    ); 
 
                } 
 
            }) 
 
            .catch(error => { 
 
                console.error( 
                    "Service Worker registration failed:", 
                    error 
                ); 
 
            }); 
 
    }); 
 
} 
 
 
// ========================================== 
// POLAR COMMAND - Notification Helper 
// ========================================== 
 
function showPolarNotification(title, message) { 
 
    if (!("Notification" in window)) { 
 
        console.log( 
            "POLAR COMMAND: Notifications not supported." 
        ); 
 
        return; 
    } 
 
    if (Notification.permission === "granted") { 
 
        new Notification(title, { 
            body: message 
        }); 
 
    } 
 
    else if (Notification.permission === "default") { 
 
        Notification.requestPermission().then(permission => { 
 
            if (permission === "granted") { 
 
                new Notification(title, { 
                    body: message 
                }); 
 
            } 
 
        }); 
 
    } 
 
    else { 
 
        console.log( 
            "POLAR COMMAND: Notification permission denied." 
        ); 
 
    } 
 
} 


// ==========================================
// POLAR COMMAND - BACKGROUND SYNC MESSAGE
// ==========================================

if ("serviceWorker" in navigator) {

    navigator.serviceWorker.addEventListener(
        "message",
        event => {

            if (
                event.data &&
                event.data.type ===
                "POLAR_BACKGROUND_SYNC"
            ) {

                console.log(
                    "POLAR COMMAND: Background Sync message received."
                );

                if (
                    typeof syncPendingChanges ===
                    "function"
                ) {

                    syncPendingChanges();

                }

            }

        }
    );

}
