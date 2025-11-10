document.addEventListener('DOMContentLoaded', function() {
    const messages = document.querySelectorAll('.message');
    
    messages.forEach(function(message, index) {
        // Stagger the auto-hide timing if multiple messages
        setTimeout(function() {
            hideMessage(message);
        }, 5000 + (index * 500));
    });
});

function closeMessage(button) {
    const message = button.closest('.message');
    hideMessage(message);
}

function hideMessage(message) {
    message.classList.add('fade-out');
    setTimeout(function() {
        if (message.parentNode) {
            message.parentNode.removeChild(message);
        }
    }, 300);
}

// Close message on click (optional)
document.addEventListener('click', function(e) {
    if (e.target.closest('.message-content')) {
        const message = e.target.closest('.message');
        hideMessage(message);
    }
});


function showButtonLoader(button) {
    button.classList.add('loading');
}

// Function to hide loader on button
function hideButtonLoader(button) {
    button.classList.remove('loading');
}

// Function to initialize button loaders
function initializeButtonLoaders() {
    // Add event listeners to forms
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitButton = this.querySelector('button[type="submit"].btn-loader');
            if (submitButton) {
                showButtonLoader(submitButton);
            }
        });
    });
    
    // Manual control for specific buttons
    const saveStylistBtn = document.getElementById('saveStylistBtn');
    const createAppointmentBtn = document.getElementById('createAppointmentBtn');
    const saveStyleBtn = document.getElementById('saveStyleBtn');
    
    // Example of manual control if needed
    if (saveStylistBtn) {
        saveStylistBtn.addEventListener('click', function() {
            showButtonLoader(this);
        });
    }
    
    if (createAppointmentBtn) {
        createAppointmentBtn.addEventListener('click', function() {
            showButtonLoader(this);
        });
    }
    
    if (saveStyleBtn) {
        saveStyleBtn.addEventListener('click', function() {
            showButtonLoader(this);
        });
    }
}

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', function() {
    initializeButtonLoaders();
});

// For AJAX forms - hide loader when request completes
function handleAjaxForm(button, promise) {
    showButtonLoader(button);
    promise.finally(() => {
        hideButtonLoader(button);
    });
}

