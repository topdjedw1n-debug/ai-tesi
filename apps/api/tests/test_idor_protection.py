"""
IDOR (Insecure Direct Object Reference) Protection Tests

Tests that users cannot access other users' resources.
"""
import pytest

from app.core.exceptions import NotFoundError
from app.models.auth import User
from app.models.document import Document
from app.models.payment import Payment
from app.services.document_service import DocumentService
from app.services.payment_service import PaymentService


@pytest.mark.asyncio
async def test_document_access_different_user(db_session):
    """Test that user1 cannot access user2's document"""
    # Create user1
    user1 = User(email="user1@example.com", full_name="User 1")
    db_session.add(user1)
    
    # Create user2
    user2 = User(email="user2@example.com", full_name="User 2")
    db_session.add(user2)
    
    await db_session.commit()
    await db_session.refresh(user1)
    await db_session.refresh(user2)
    
    # Create document for user2
    document = Document(
        user_id=user2.id,
        title="User 2's Document",
        topic="Secret Topic",
        status="draft"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    
    # user1 tries to access user2's document - should get 404
    service = DocumentService(db_session)
    
    with pytest.raises(NotFoundError, match="Document not found"):
        await service.check_document_ownership(document.id, user1.id)


@pytest.mark.asyncio
async def test_document_update_different_user(db_session):
    """Test that user1 cannot update user2's document"""
    # Create users
    user1 = User(email="user1@example.com", full_name="User 1")
    user2 = User(email="user2@example.com", full_name="User 2")
    db_session.add_all([user1, user2])
    await db_session.commit()
    await db_session.refresh(user1)
    await db_session.refresh(user2)
    
    # Create document for user2
    document = Document(
        user_id=user2.id,
        title="User 2's Document",
        topic="Secret Topic",
        status="draft"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    
    # user1 tries to update user2's document
    service = DocumentService(db_session)
    
    with pytest.raises(NotFoundError, match="Document not found"):
        await service.check_document_ownership(document.id, user1.id)


@pytest.mark.asyncio
async def test_document_delete_different_user(db_session):
    """Test that user1 cannot delete user2's document"""
    # Create users
    user1 = User(email="user1@example.com", full_name="User 1")
    user2 = User(email="user2@example.com", full_name="User 2")
    db_session.add_all([user1, user2])
    await db_session.commit()
    await db_session.refresh(user1)
    await db_session.refresh(user2)
    
    # Create document for user2
    document = Document(
        user_id=user2.id,
        title="User 2's Document",
        topic="Secret Topic",
        status="draft"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    
    # user1 tries to delete user2's document
    service = DocumentService(db_session)
    
    with pytest.raises(NotFoundError, match="Document not found"):
        await service.check_document_ownership(document.id, user1.id)


@pytest.mark.asyncio
async def test_document_export_different_user(db_session):
    """Test that user1 cannot export user2's document"""
    # Create users
    user1 = User(email="user1@example.com", full_name="User 1")
    user2 = User(email="user2@example.com", full_name="User 2")
    db_session.add_all([user1, user2])
    await db_session.commit()
    await db_session.refresh(user1)
    await db_session.refresh(user2)
    
    # Create document for user2
    document = Document(
        user_id=user2.id,
        title="User 2's Document",
        topic="Secret Topic",
        status="completed",
        content="Secret content"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    
    # user1 tries to export user2's document
    service = DocumentService(db_session)
    
    with pytest.raises(NotFoundError, match="Document not found"):
        await service.check_document_ownership(document.id, user1.id)


@pytest.mark.asyncio
async def test_document_owner_can_access(db_session):
    """Test that document owner can still access their document"""
    # Create user
    user = User(email="owner@example.com", full_name="Owner")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Create document for user
    document = Document(
        user_id=user.id,
        title="My Document",
        topic="My Topic",
        status="draft"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    
    # Owner should be able to access
    service = DocumentService(db_session)
    result = await service.check_document_ownership(document.id, user.id)
    
    assert result.id == document.id
    assert result.user_id == user.id


@pytest.mark.asyncio
async def test_payment_access_different_user(db_session):
    """Test that user1 cannot access user2's payment"""
    # Create users
    user1 = User(email="user1@example.com", full_name="User 1")
    user2 = User(email="user2@example.com", full_name="User 2")
    db_session.add_all([user1, user2])
    await db_session.commit()
    await db_session.refresh(user1)
    await db_session.refresh(user2)
    
    # Create payment for user2
    payment = Payment(
        user_id=user2.id,
        stripe_payment_intent_id="pi_test_123",
        amount=100.00,
        currency="EUR",
        status="completed"
    )
    db_session.add(payment)
    await db_session.commit()
    await db_session.refresh(payment)
    
    # user1 tries to access user2's payment - should get 404
    service = PaymentService(db_session)
    
    with pytest.raises(ValueError, match="Payment not found"):
        await service.check_payment_ownership(payment.id, user1.id)


@pytest.mark.asyncio
async def test_payment_owner_can_access(db_session):
    """Test that payment owner can still access their payment"""
    # Create user
    user = User(email="owner@example.com", full_name="Owner")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Create payment for user
    payment = Payment(
        user_id=user.id,
        stripe_payment_intent_id="pi_test_123",
        amount=100.00,
        currency="EUR",
        status="completed"
    )
    db_session.add(payment)
    await db_session.commit()
    await db_session.refresh(payment)
    
    # Owner should be able to access
    service = PaymentService(db_session)
    result = await service.check_payment_ownership(payment.id, user.id)
    
    assert result.id == payment.id
    assert result.user_id == user.id


@pytest.mark.asyncio
async def test_nonexistent_document_access(db_session):
    """Test that accessing non-existent document returns 404"""
    # Create user
    user = User(email="user@example.com", full_name="User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Try to access non-existent document
    service = DocumentService(db_session)
    
    with pytest.raises(NotFoundError, match="Document not found"):
        await service.check_document_ownership(99999, user.id)


@pytest.mark.asyncio
async def test_nonexistent_payment_access(db_session):
    """Test that accessing non-existent payment returns 404"""
    # Create user
    user = User(email="user@example.com", full_name="User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Try to access non-existent payment
    service = PaymentService(db_session)
    
    with pytest.raises(ValueError, match="Payment not found"):
        await service.check_payment_ownership(99999, user.id)

