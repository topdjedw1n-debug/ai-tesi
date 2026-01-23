"""
Email notification service for sending emails to users and admins
Uses fastapi-mail for async email sending
"""

import logging

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending email notifications"""

    def __init__(self) -> None:
        """Initialize email service with SMTP configuration"""
        self.fastmail: FastMail | None = None

        # Only initialize if SMTP is configured
        if self.is_configured():
            try:
                self.connection_config = ConnectionConfig(
                    MAIL_USERNAME=settings.SMTP_USER or "",
                    MAIL_PASSWORD=settings.SMTP_PASSWORD or "",
                    MAIL_FROM=settings.EMAILS_FROM_EMAIL
                    or settings.SMTP_USER
                    or "noreply@tesigo.com",
                    MAIL_FROM_NAME=settings.EMAILS_FROM_NAME or "TesiGo Platform",
                    MAIL_PORT=settings.SMTP_PORT or 587,
                    MAIL_SERVER=settings.SMTP_HOST or "localhost",
                    MAIL_STARTTLS=settings.SMTP_TLS,
                    MAIL_SSL_TLS=False,  # Use STARTTLS instead
                    USE_CREDENTIALS=True,
                    VALIDATE_CERTS=True,
                )
                self.fastmail = FastMail(self.connection_config)
                logger.info("✅ Email service initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize email service: {e}")
                self.fastmail = None
        else:
            logger.warning(
                "⚠️ Email service not configured. Set SMTP_HOST in .env to enable emails."
            )

    def is_configured(self) -> bool:
        """Check if email service is configured"""
        return bool(
            settings.SMTP_HOST
            and settings.SMTP_USER
            and settings.SMTP_PASSWORD
            and settings.SMTP_PORT
        )

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str | None = None,
        text_body: str | None = None,
    ) -> bool:
        """
        Send email to recipient

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML content (optional)
            text_body: Plain text content (optional)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_configured():
            logger.warning(
                f"⚠️ Email not sent to {to_email}: SMTP not configured. "
                f"Subject: {subject}"
            )
            return False

        if not self.fastmail:
            logger.error("❌ Email service not initialized")
            return False

        try:
            # If no body provided, use text_body as fallback
            if not html_body and not text_body:
                logger.error("❌ Cannot send email: no body provided")
                return False

            message = MessageSchema(
                subject=subject,
                recipients=[to_email],
                body=html_body or text_body,
                subtype=MessageType.html if html_body else MessageType.plain,
            )

            await self.fastmail.send_message(message)
            logger.info(f"✅ Email sent successfully to {to_email}: {subject}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to send email to {to_email}: {e}", exc_info=True)
            return False

    async def send_magic_link(self, email: str, magic_link: str, token: str) -> bool:
        """
        Send magic link email for passwordless authentication

        Args:
            email: Recipient email
            magic_link: Full magic link URL
            token: Magic link token (for fallback)

        Returns:
            True if sent successfully
        """
        subject = "🔐 Your TesiGo Login Link"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #2563eb;
                          color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .button:hover {{ background-color: #1d4ed8; }}
                .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Welcome to TesiGo! 👋</h2>
                <p>Click the button below to log in to your account:</p>
                <a href="{magic_link}" class="button">Login to TesiGo</a>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #2563eb;">{magic_link}</p>
                <p><strong>This link expires in 15 minutes.</strong></p>
                <p>If you didn't request this link, you can safely ignore this email.</p>
                <div class="footer">
                    <p>© TesiGo Platform | AI-Powered Thesis Generation</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""
        Welcome to TesiGo!

        Click this link to log in to your account:
        {magic_link}

        This link expires in 15 minutes.

        If you didn't request this link, you can safely ignore this email.

        © TesiGo Platform
        """

        return await self.send_email(
            to_email=email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

    async def send_document_ready_notification(
        self, email: str, document_title: str, document_id: int
    ) -> bool:
        """
        Send notification when document generation is complete

        Args:
            email: Recipient email
            document_title: Title of the completed document
            document_id: ID of the document

        Returns:
            True if sent successfully
        """
        subject = f"✅ Your document '{document_title}' is ready!"

        document_url = f"{settings.FRONTEND_URL}/dashboard/documents/{document_id}"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #10b981;
                          color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .button:hover {{ background-color: #059669; }}
                .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>🎉 Your document is ready!</h2>
                <p>Great news! Your document <strong>"{document_title}"</strong> has been successfully generated.</p>
                <a href="{document_url}" class="button">View Document</a>
                <p>Or copy and paste this link:</p>
                <p style="word-break: break-all; color: #2563eb;">{document_url}</p>
                <p>You can now download, edit, or share your document from your dashboard.</p>
                <div class="footer">
                    <p>© TesiGo Platform | AI-Powered Thesis Generation</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""
        Your document is ready!

        Your document "{document_title}" has been successfully generated.

        View your document:
        {document_url}

        You can now download, edit, or share your document from your dashboard.

        © TesiGo Platform
        """

        return await self.send_email(
            to_email=email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

    async def send_document_failed_notification(
        self, email: str, document_title: str, error_message: str | None = None
    ) -> bool:
        """
        Send notification when document generation fails

        Args:
            email: Recipient email
            document_title: Title of the failed document
            error_message: Optional error message

        Returns:
            True if sent successfully
        """
        subject = f"❌ Issue with your document '{document_title}'"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .error-box {{ background-color: #fef2f2; border-left: 4px solid #ef4444;
                             padding: 15px; margin: 20px 0; }}
                .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>⚠️ Document Generation Issue</h2>
                <p>We encountered an issue while generating your document <strong>"{document_title}"</strong>.</p>
                <div class="error-box">
                    <p><strong>What happened?</strong></p>
                    <p>{error_message or "An unexpected error occurred during document generation."}</p>
                </div>
                <p>Please try creating a new document or contact our support if the issue persists.</p>
                <p>We apologize for any inconvenience.</p>
                <div class="footer">
                    <p>© TesiGo Platform | AI-Powered Thesis Generation</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""
        Document Generation Issue

        We encountered an issue while generating your document "{document_title}".

        Error: {error_message or "An unexpected error occurred during document generation."}

        Please try creating a new document or contact our support if the issue persists.

        © TesiGo Platform
        """

        return await self.send_email(
            to_email=email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

    async def notify_admins_refund_request(
        self,
        admin_emails: list[str],
        refund_request_id: int,
        user_email: str,
        amount: str,
    ) -> bool:
        """
        Notify admins about new refund request

        Args:
            admin_emails: List of admin email addresses
            refund_request_id: ID of the refund request
            user_email: Email of the user requesting refund
            amount: Refund amount

        Returns:
            True if sent successfully
        """
        if not admin_emails:
            logger.warning("⚠️ No admin emails provided for refund notification")
            return False

        subject = f"💰 New Refund Request #{refund_request_id}"

        admin_url = f"{settings.FRONTEND_URL}/admin/refunds/{refund_request_id}"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .info-box {{ background-color: #eff6ff; border-left: 4px solid #2563eb;
                            padding: 15px; margin: 20px 0; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #2563eb;
                          color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .button:hover {{ background-color: #1d4ed8; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>💰 New Refund Request</h2>
                <div class="info-box">
                    <p><strong>Request ID:</strong> #{refund_request_id}</p>
                    <p><strong>User:</strong> {user_email}</p>
                    <p><strong>Amount:</strong> {amount}</p>
                </div>
                <a href="{admin_url}" class="button">Review Request</a>
                <p>Please review and process this refund request as soon as possible.</p>
            </div>
        </body>
        </html>
        """

        text_body = f"""
        New Refund Request

        Request ID: #{refund_request_id}
        User: {user_email}
        Amount: {amount}

        Review: {admin_url}

        Please review and process this refund request as soon as possible.
        """

        # Send to all admins
        success_count = 0
        for admin_email in admin_emails:
            if await self.send_email(
                to_email=admin_email,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            ):
                success_count += 1

        return success_count > 0

    async def send_refund_approved_notification(
        self, email: str, refund_request_id: int, amount: str
    ) -> bool:
        """Send notification when refund is approved"""
        subject = f"✅ Refund Approved - Request #{refund_request_id}"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .success-box {{ background-color: #f0fdf4; border-left: 4px solid #10b981;
                               padding: 15px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>✅ Refund Approved</h2>
                <div class="success-box">
                    <p><strong>Request ID:</strong> #{refund_request_id}</p>
                    <p><strong>Amount:</strong> {amount}</p>
                </div>
                <p>Your refund request has been approved and the amount will be refunded to your original payment method within 5-10 business days.</p>
            </div>
        </body>
        </html>
        """

        return await self.send_email(
            to_email=email, subject=subject, html_body=html_body
        )

    async def send_refund_rejected_notification(
        self, email: str, refund_request_id: int, reason: str | None = None
    ) -> bool:
        """Send notification when refund is rejected"""
        subject = f"❌ Refund Request #{refund_request_id} - Status Update"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .info-box {{ background-color: #fffbeb; border-left: 4px solid #f59e0b;
                            padding: 15px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Refund Request Status Update</h2>
                <div class="info-box">
                    <p><strong>Request ID:</strong> #{refund_request_id}</p>
                    <p><strong>Status:</strong> Rejected</p>
                    {f'<p><strong>Reason:</strong> {reason}</p>' if reason else ''}
                </div>
                <p>If you have any questions, please contact our support team.</p>
            </div>
        </body>
        </html>
        """

        return await self.send_email(
            to_email=email, subject=subject, html_body=html_body
        )


# Global instance
notification_service = NotificationService()
