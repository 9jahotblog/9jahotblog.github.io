document.addEventListener('DOMContentLoaded', () => {
    // Load the sidebar HTML
    fetch('sidebar.html')
        .then(response => response.text())
        .then(data => {
            document.getElementById('sidebar-placeholder').innerHTML = data;

            // Initialize sidebar functionality
            initializeSidebar();
        });
});

function initializeSidebar() {
    // Firebase authentication setup
    import { getAuth, onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/10.12.4/firebase-auth.js";

    const auth = getAuth();

    // Check if user is signed in and display their info
    onAuthStateChanged(auth, (user) => {
        if (user) {
            document.getElementById('user-name-sidebar').textContent = `You're logged in as ${user.displayName || 'User'}`;
            document.getElementById('user-username-sidebar').textContent = user.displayName || 'Username';
            if (user.photoURL) {
                document.getElementById('profile-photo-sidebar').src = user.photoURL;
            }
            document.getElementById('sidebar').style.display = 'block';
        } else {
            document.getElementById('sidebar').style.display = 'none';
        }
    });

    // Logout function
    document.getElementById('logout-sidebar').addEventListener('click', () => {
        signOut(auth).then(() => {
            window.location.href = 'login-page.html';
        });
    });
}

<!-- Firebase SDKs -->
<script src="https://www.gstatic.com/firebasejs/10.12.4/firebase-app.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.12.4/firebase-auth.js"></script>

<!-- Sidebar script -->
<script src="sidebar.js"></script>
