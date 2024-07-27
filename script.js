import { getAuth, signInWithEmailAndPassword } from 'firebase/auth';
import app from './firebase.js'; // Assuming your firebaseConfig is in firebase.js

const auth = getAuth(app);
const loginForm = document.getElementById('loginForm');

loginForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const email = document.getElementById('email').value;
  const password = document.getElementById('password').value;

  signInWithEmailAndPassword(auth, email, password)
    .then((userCredential) => {
      // Signed in
      console.log('User signed in successfully:', userCredential.user);
      // Redirect to the desired page after successful login
    })
    .catch((error) => {
      // Handle errors
      console.error('Error signing in:', error);
      // Display an error message to the user
    });
});
