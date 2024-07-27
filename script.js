import { getAuth, createUserWithEmailAndPassword, signInWithEmailAndPassword, sendPasswordResetEmail, sendEmailVerification, GoogleAuthProvider, signInWithPopup } from 'firebase/auth';
import app from './firebase.js';

const auth = getAuth(app);
const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');
const forgotPasswordLink = document.getElementById('forgotPasswordLink');
const googleSignInButton = document.getElementById('googleSignInButton');
const googleProvider = new GoogleAuthProvider();

// Functions for displaying success/error messages
const showSuccessMessage = (message) => {
  // Replace with your desired success message display logic
  console.log('Success:', message);
};

const showErrorMessage = (message) => {
  // Replace with your desired error message display logic
  console.error('Error:', message);
};

// Login functionality
loginForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const email = document.getElementById('email').value;
  const password = document.getElementById('password').value;

  signInWithEmailAndPassword(auth, email, password)
    .then((userCredential) => {
      // Signed in
      const user = userCredential.user;
      showSuccessMessage('Login successful!');
      // Redirect to desired page after successful login
    })
    .catch((error) => {
      const errorCode = error.code;
      const errorMessage = error.message;
      showErrorMessage(errorMessage);
    });
});

// Register functionality
registerForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const email = document.getElementById('registerEmail').value;
  const password = document.getElementById('registerPassword').value;

  createUserWithEmailAndPassword(auth, email, password)
    .then((userCredential) => {
      // Send verification email
      sendEmailVerification(auth.currentUser)
        .then(() => {
          showSuccessMessage('User created successfully. Verification email sent.');
          // Redirect to confirmation page or display a message
        })
        .catch((error) => {
          showErrorMessage('Error sending verification email:', error);
        });
    })
    .catch((error) => {
      const errorCode = error.code;
      const errorMessage = error.message;
      showErrorMessage(errorMessage);
    });
});

// Forgot password functionality
forgotPasswordLink.addEventListener('click', (event) => {
  event.preventDefault();
  const email = document.getElementById('email').value;

  sendPasswordResetEmail(auth, email)
    .then(() => {
      showSuccessMessage('Password reset email sent.');
    })
    .catch((error) => {
      showErrorMessage('Error sending password reset email:', error);
    });
});

// Google Sign-In
googleSignInButton.addEventListener('click', () => {
  signInWithPopup(auth, googleProvider)
    .then((result) => {
      const user = result.user;
      showSuccessMessage('Signed in with Google!');
      // Handle user data and redirect
    })
    .catch((error) => {
      const errorCode = error.code;
      const errorMessage = error.message;
      showErrorMessage(errorMessage);
    });
});
