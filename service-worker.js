const CACHE_NAME = "polar-command-v1";

const STATIC_ASSETS = [
    "/static/css/style.css",
    "/static/js/script.js",
    "/static/js/offline.js"
];

self.addEventListener("install", event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(STATIC_ASSETS))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener("activate", event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys
                    .filter(key => key !== CACHE_NAME)
                    .map(key => caches.delete(key))
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener("fetch", event => {

    if (event.request.method !== "GET") {
        return;
    }

    event.respondWith(
        fetch(event.request)
            .then(response => {

                const responseClone = response.clone();

                caches.open(CACHE_NAME).then(cache => {
                    cache.put(event.request, responseClone);
                });

                return response;
            })
            .catch(() => {
                return caches.match(event.request)
                    .then(cachedResponse => {

                        if (cachedResponse) {
                            return cachedResponse;
                        }

                        if (event.request.mode === "navigate") {
                            return new Response(
                                `
                                <!DOCTYPE html>
                                <html>
                                <head>
                                    <title>POLAR COMMAND - Offline</title>
                                    <meta name="viewport"
                                          content="width=device-width, initial-scale=1">
                                    <style>
                                        body {
                                            font-family: Arial, sans-serif;
                                            text-align: center;
                                            padding: 60px 20px;
                                            background: #f4f8fc;
                                            color: #102a43;
                                        }

                                        .box {
                                            max-width: 500px;
                                            margin: auto;
                                            padding: 35px;
                                            background: white;
                                            border-radius: 16px;
                                            box-shadow: 0 5px 20px rgba(0,0,0,0.08);
                                        }

                                        h1 {
                                            margin-bottom: 10px;
                                        }

                                        p {
                                            color: #52606d;
                                            line-height: 1.6;
                                        }

                                        .status {
                                            display: inline-block;
                                            padding: 8px 16px;
                                            border-radius: 20px;
                                            background: #fff3cd;
                                            color: #856404;
                                            margin-top: 15px;
                                        }
                                    </style>
                                </head>

                                <body>

                                    <div class="box">

                                        <h1>POLAR COMMAND</h1>

                                        <h2>Offline Mode</h2>

                                        <p>
                                            Internet connection is currently unavailable.
                                            The application will continue using
                                            locally cached resources.
                                        </p>

                                        <div class="status">
                                            Waiting for connection...
                                        </div>

                                    </div>

                                </body>
                                </html>
                                `,
                                {
                                    headers: {
                                        "Content-Type": "text/html"
                                    }
                                }
                            );
                        }
                    });
            })
    );
});

// ==========================================
// POLAR COMMAND - BACKGROUND SYNC
// ==========================================

self.addEventListener("sync", event => {

    if (event.tag === "polar-pending-sync") {

        console.log(
            "POLAR COMMAND: Background Sync triggered."
        );

        event.waitUntil(

            self.clients.matchAll({
                includeUncontrolled: true,
                type: "window"
            }).then(clients => {

                clients.forEach(client => {

                    client.postMessage({
                        type: "POLAR_BACKGROUND_SYNC"
                    });

                });

            })

        );

    }

});