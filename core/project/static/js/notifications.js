document.addEventListener('DOMContentLoaded', function () {
    var videos = document.querySelectorAll('.post-video');
    videos.forEach(function(video) {
        video.addEventListener('play', function() {
            videos.forEach(function(v) {
                if (v !== video) v.pause();
            });
        });
    });

    function resetForm() {
        document.querySelector('form').reset();
        window.location.href = "{% url 'index' %}";
    }

    function updateNotificationCount() {
        fetch('{% url "get_unread_notifications_count" %}')
            .then(response => response.json())
            .then(data => {
                updateBadge(data.count);
            });
    }
    
    function updateBadge(count) {
        const badge = document.querySelector('.notification-icon .badge');
        if (count > 0) {
            if (badge) {
                badge.textContent = count;
            } else {
                const newBadge = document.createElement('span');
                newBadge.className = 'badge';
                newBadge.textContent = count;
                document.querySelector('.notification-icon a').appendChild(newBadge);
            }
        } else if (badge) {
            badge.remove();
        }
    }
    
    // Update notification count when the page loads
    updateNotificationCount();
    
    // Add click event listener to the notification bell
    document.querySelector('.notification-icon a').addEventListener('click', function(e) {
        e.preventDefault();
        
        // Mark notifications as read
        fetch('{% url "mark_notifications_read" %}', {
            method: 'POST',
            headers: {
                'X-CSRFToken': '{{ csrf_token }}'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // Reset the badge
                updateBadge(0);
                
                // Redirect to the notifications page
                window.location.href = this.href;
            }
        });
    });

    const notificationBell = document.getElementById('notification-bell');
    const notificationsContainer = document.getElementById('notifications-container');
    const notificationList = document.getElementById('notification-list');

    notificationBell.addEventListener('click', function (e) {
        e.preventDefault();
        if (notificationsContainer.style.display === 'none' || notificationsContainer.style.display === '') {
            notificationsContainer.style.display = 'block';
            fetchNotifications();
        } else {
            notificationsContainer.style.display = 'none';
        }
    });

    function fetchNotifications() {
        fetch('{% url "get_notifications" %}')
            .then(response => response.json())
            .then(data => {
                notificationList.innerHTML = '';
                if (data.notifications.length > 0) {
                    data.notifications.forEach(notification => {
                        const li = document.createElement('li');
                        li.innerHTML = `
                            <div class="notification-item">
                                <strong>${notification.sender}</strong> sent you a message.
                                <p>${notification.content}</p>
                                <span class="timestamp">${notification.timestamp}</span>
                                <a href="${notification.chat_url}">View Message</a>
                            </div>
                        `;
                        notificationList.appendChild(li);
                    });
                } else {
                    notificationList.innerHTML = '<li>No notifications.</li>';
                }

                // Mark notifications as read
                fetch('{% url "mark_notifications_read" %}', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': '{{ csrf_token }}'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        updateNotificationCount(0);
                    }
                });
            });        
    }

    function updateNotificationCount(count) {
        const badge = document.querySelector('.notification-icon .badge');
        if (count > 0) {
            if (badge) {
                badge.textContent = count;
                badge.style.display = 'inline';
            } else {
                const newBadge = document.createElement('span');
                newBadge.className = 'badge';
                newBadge.textContent = count;
                notificationBell.appendChild(newBadge);
            }
        } else if (badge) {
            badge.style.display = 'none';
        }
    }

    // Update notification count when the page loads
    fetch('{% url "get_unread_notifications_count" %}')
        .then(response => response.json())
        .then(data => {
            updateNotificationCount(data.count);
        });
});

<div class="notifications-container" id="notifications-container" style="display: none;">
<h2>Notifications</h2>
<ul class="notification-list" id="notification-list">
</ul>
</div>