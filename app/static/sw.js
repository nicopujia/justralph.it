self.addEventListener('push', function(event) {
    var data = event.data ? event.data.text() : 'Ralph has an update for you.';
    event.waitUntil(
        self.registration.showNotification('just-ralph-it', {
            body: data,
            icon: null
        })
    );
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    event.waitUntil(
        clients.openWindow('/')
    );
});
