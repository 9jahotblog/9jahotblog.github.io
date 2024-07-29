<?php
if ($_SERVER["REQUEST_METHOD"] == "POST") {
    $name = htmlspecialchars($_POST['name']);
    $email = htmlspecialchars($_POST['email']);
    $message = htmlspecialchars($_POST['message']);
    
    $recipient = "9jahotblog2@gmail.com"; // Replace with your email address
    $subject = "New Form Submission";
    $headers = "From: no-reply@example.com\r\n";
    $headers .= "Reply-To: $email\r\n";
    $headers .= "Content-Type: text/html; charset=UTF-8\r\n";

    $email_body = "<html><body>";
    $email_body .= "<h2>New Form Submission</h2>";
    $email_body .= "<p><strong>Name:</strong> $name</p>";
    $email_body .= "<p><strong>Email:</strong> $email</p>";
    $email_body .= "<p><strong>Message:</strong> $message</p>";
    $email_body .= "</body></html>";

    // Send notification email
    mail($recipient, $subject, $email_body, $headers);

    // Send confirmation email to user
    $confirmation_subject = "Thank you for your submission";
    $confirmation_body = "<html><body>";
    $confirmation_body .= "<h2>Thank you, $name!</h2>";
    $confirmation_body .= "<p>We have received your message and will get back to you shortly.</p>";
    $confirmation_body .= "<p><strong>Your Message:</strong></p>";
    $confirmation_body .= "<p>$message</p>";
    $confirmation_body .= "</body></html>";

    mail($email, $confirmation_subject, $confirmation_body, $headers);

    echo "Thank you for your submission!";
}
?>
