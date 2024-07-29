

import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.4/firebase-app.js";
import { getAuth, onAuthStateChanged, signOut, updateProfile } from "https://www.gstatic.com/firebasejs/10.12.4/firebase-auth.js";
import { getFirestore, doc, getDoc, updateDoc } from "https://www.gstatic.com/firebasejs/10.12.4/firebase-firestore.js";

const firebaseConfig = {
    apiKey: "AIzaSyCzajY4QIxiRiob2ho-Cgkj6EtOz83AzI8",
      authDomain: "jahotblog-login.firebaseapp.com",
      projectId: "jahotblog-login",
      storageBucket: "jahotblog-login.appspot.com",
      messagingSenderId: "661526730601",
      appId: "1:661526730601:web:27a3c1624ccd6f20ab8ff8"
    };

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

export function loadProfile() {
    // Check if user is signed in and display their info
    onAuthStateChanged(auth, (user) => {
        if (user) {
            document.getElementById('user-name').textContent = user.displayName || 'User';
            document.getElementById('user-email').textContent = user.email;
            document.getElementById('user-username').textContent = user.displayName || 'Username';
            if (user.photoURL) {
                document.getElementById('profile-photo').src = user.photoURL;
            }
        } else {
            window.location.href = 'login-page.html';
        }
    });

    // Logout function
    document.getElementById('logout').addEventListener('click', () => {
        signOut(auth).then(() => {
            window.location.href = 'login-page.html';
        });
    });

    // Edit profile function
    document.getElementById('edit-profile').addEventListener('click', async () => {
        const newFullname = prompt("Enter new full name:");
        const newUsername = prompt("Enter new username:");
        const newPhotoURL = prompt("Enter new profile photo URL:");

        if (auth.currentUser) {
            if (newFullname) {
                await updateProfile(auth.currentUser, { displayName: newFullname });
            }
            if (newUsername) {
                await updateProfile(auth.currentUser, { displayName: newUsername });
            }
            if (newPhotoURL) {
                await updateProfile(auth.currentUser, { photoURL: newPhotoURL });
                document.getElementById('profile-photo').src = newPhotoURL;
            }

            const userRef = doc(db, "users", auth.currentUser.uid);
            await updateDoc(userRef, {
                fullname: newFullname || auth.currentUser.displayName,
                username: newUsername || auth.currentUser.displayName,
                photoURL: newPhotoURL || auth.currentUser.photoURL
            });

            alert("Profile updated successfully!");
            location.reload();
        }
    });
}
