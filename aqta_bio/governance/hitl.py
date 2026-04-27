"""
Human-in-the-Loop (HITL) Sign-off Module

Implements Requirement 6.4:
"WHEN a Tile enters the top-1% risk tier, THE Governance_Gateway SHALL
require epidemiologist sign-off before any external alert is issued for that Tile."

This module provides:
- Database models for sign-off tracking
- Service layer for creating, approving, and querying sign-offs
- Integration with GovernanceGateway
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    Integer,
    Column,
    DateTime,
    Float,
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class SignoffStatus(str, Enum):
    """Sign-off approval status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class HITLSignoff(Base):
    """
    Database model for HITL sign-off records.
    
    Tracks epidemiologist approval/rejection of high-risk tiles
    before external alerts can be issued.
    """
    __tablename__ = "hitl_signoffs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tile_id = Column(String(12), nullable=False)
    pathogen_id = Column(String(20), nullable=False, default="ebola")
    month = Column(String(7), nullable=False)  # YYYY-MM format
    risk_score = Column(Float, nullable=False)
    status = Column(String(20), nullable=False, default=SignoffStatus.PENDING.value)
    approver_id = Column(String(100), nullable=True)
    approver_name = Column(String(200), nullable=True)
    approval_timestamp = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint("tile_id", "pathogen_id", "month", name="hitl_signoffs_unique_tile_month"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="hitl_signoffs_status_check"),
        CheckConstraint("risk_score >= 0 AND risk_score <= 1", name="hitl_signoffs_risk_score_check"),
        Index("idx_hitl_signoffs_status", "status"),
        Index("idx_hitl_signoffs_tile_id", "tile_id"),
        Index("idx_hitl_signoffs_pathogen_id", "pathogen_id"),
        Index("idx_hitl_signoffs_created_at", "created_at"),
    )


@dataclass
class SignoffRequest:
    """Request to create a new sign-off requirement"""
    tile_id: str
    pathogen_id: str
    month: str
    risk_score: float


@dataclass
class SignoffApproval:
    """Approval/rejection of a sign-off request"""
    tile_id: str
    pathogen_id: str
    month: str
    approved: bool
    approver_id: str
    approver_name: str
    rejection_reason: Optional[str] = None


@dataclass
class SignoffRecord:
    """Sign-off record for API responses"""
    id: int
    tile_id: str
    pathogen_id: str
    month: str
    risk_score: float
    status: str
    approver_id: Optional[str]
    approver_name: Optional[str]
    approval_timestamp: Optional[datetime]
    rejection_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_orm(cls, orm_obj: HITLSignoff) -> "SignoffRecord":
        """Convert ORM object to dataclass"""
        return cls(
            id=orm_obj.id,
            tile_id=orm_obj.tile_id,
            pathogen_id=orm_obj.pathogen_id,
            month=orm_obj.month,
            risk_score=orm_obj.risk_score,
            status=orm_obj.status,
            approver_id=orm_obj.approver_id,
            approver_name=orm_obj.approver_name,
            approval_timestamp=orm_obj.approval_timestamp,
            rejection_reason=orm_obj.rejection_reason,
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at,
        )


class HITLSignoffService:
    """
    Service layer for HITL sign-off operations.
    
    Provides methods to:
    - Create sign-off requirements for high-risk tiles
    - Approve or reject sign-offs
    - Query pending sign-offs
    - Check if a tile has been approved for external alerts
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_signoff_requirement(
        self,
        tile_id: str,
        pathogen_id: str,
        month: str,
        risk_score: float,
    ) -> SignoffRecord:
        """
        Create a new sign-off requirement for a high-risk tile.
        
        If a sign-off already exists for this tile-pathogen-month combination,
        returns the existing record.
        
        Args:
            tile_id: Tile identifier
            pathogen_id: Pathogen identifier
            month: Month in YYYY-MM format
            risk_score: Risk score [0, 1]
        
        Returns:
            SignoffRecord with status='pending'
        """
        # Check if sign-off already exists
        existing = self.session.query(HITLSignoff).filter_by(
            tile_id=tile_id,
            pathogen_id=pathogen_id,
            month=month,
        ).first()
        
        if existing:
            return SignoffRecord.from_orm(existing)
        
        # Create new sign-off requirement
        signoff = HITLSignoff(
            tile_id=tile_id,
            pathogen_id=pathogen_id,
            month=month,
            risk_score=risk_score,
            status=SignoffStatus.PENDING.value,
        )
        
        self.session.add(signoff)
        self.session.commit()
        self.session.refresh(signoff)
        
        return SignoffRecord.from_orm(signoff)
    
    def approve_signoff(
        self,
        tile_id: str,
        pathogen_id: str,
        month: str,
        approver_id: str,
        approver_name: str,
    ) -> SignoffRecord:
        """
        Approve a sign-off, allowing external alerts for this tile.
        
        Args:
            tile_id: Tile identifier
            pathogen_id: Pathogen identifier
            month: Month in YYYY-MM format
            approver_id: User ID of approver
            approver_name: Display name of approver
        
        Returns:
            Updated SignoffRecord with status='approved'
        
        Raises:
            ValueError: If sign-off not found or already processed
        """
        signoff = self.session.query(HITLSignoff).filter_by(
            tile_id=tile_id,
            pathogen_id=pathogen_id,
            month=month,
        ).first()
        
        if not signoff:
            raise ValueError(f"Sign-off not found for tile {tile_id}, pathogen {pathogen_id}, month {month}")
        
        if signoff.status != SignoffStatus.PENDING.value:
            raise ValueError(f"Sign-off already processed with status: {signoff.status}")
        
        signoff.status = SignoffStatus.APPROVED.value
        signoff.approver_id = approver_id
        signoff.approver_name = approver_name
        signoff.approval_timestamp = datetime.utcnow()
        
        self.session.commit()
        self.session.refresh(signoff)
        
        return SignoffRecord.from_orm(signoff)
    
    def reject_signoff(
        self,
        tile_id: str,
        pathogen_id: str,
        month: str,
        approver_id: str,
        approver_name: str,
        rejection_reason: str,
    ) -> SignoffRecord:
        """
        Reject a sign-off, suppressing external alerts for this tile.
        
        Args:
            tile_id: Tile identifier
            pathogen_id: Pathogen identifier
            month: Month in YYYY-MM format
            approver_id: User ID of approver
            approver_name: Display name of approver
            rejection_reason: Reason for rejection
        
        Returns:
            Updated SignoffRecord with status='rejected'
        
        Raises:
            ValueError: If sign-off not found or already processed
        """
        signoff = self.session.query(HITLSignoff).filter_by(
            tile_id=tile_id,
            pathogen_id=pathogen_id,
            month=month,
        ).first()
        
        if not signoff:
            raise ValueError(f"Sign-off not found for tile {tile_id}, pathogen {pathogen_id}, month {month}")
        
        if signoff.status != SignoffStatus.PENDING.value:
            raise ValueError(f"Sign-off already processed with status: {signoff.status}")
        
        signoff.status = SignoffStatus.REJECTED.value
        signoff.approver_id = approver_id
        signoff.approver_name = approver_name
        signoff.approval_timestamp = datetime.utcnow()
        signoff.rejection_reason = rejection_reason
        
        self.session.commit()
        self.session.refresh(signoff)
        
        return SignoffRecord.from_orm(signoff)
    
    def get_pending_signoffs(
        self,
        pathogen_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[SignoffRecord]:
        """
        Get all pending sign-offs, optionally filtered by pathogen.
        
        Args:
            pathogen_id: Optional pathogen filter
            limit: Maximum number of records to return
        
        Returns:
            List of SignoffRecords with status='pending', ordered by created_at DESC
        """
        query = self.session.query(HITLSignoff).filter_by(status=SignoffStatus.PENDING.value)
        
        if pathogen_id:
            query = query.filter_by(pathogen_id=pathogen_id)
        
        query = query.order_by(HITLSignoff.created_at.desc()).limit(limit)
        
        return [SignoffRecord.from_orm(s) for s in query.all()]
    
    def get_signoff_status(
        self,
        tile_id: str,
        pathogen_id: str,
        month: str,
    ) -> Optional[SignoffRecord]:
        """
        Get the sign-off status for a specific tile-pathogen-month.
        
        Args:
            tile_id: Tile identifier
            pathogen_id: Pathogen identifier
            month: Month in YYYY-MM format
        
        Returns:
            SignoffRecord if exists, None otherwise
        """
        signoff = self.session.query(HITLSignoff).filter_by(
            tile_id=tile_id,
            pathogen_id=pathogen_id,
            month=month,
        ).first()
        
        if signoff:
            return SignoffRecord.from_orm(signoff)
        
        return None
    
    def is_approved_for_alert(
        self,
        tile_id: str,
        pathogen_id: str,
        month: str,
    ) -> bool:
        """
        Check if a tile has been approved for external alerts.
        
        Args:
            tile_id: Tile identifier
            pathogen_id: Pathogen identifier
            month: Month in YYYY-MM format
        
        Returns:
            True if approved, False if pending or rejected or not found
        """
        signoff = self.get_signoff_status(tile_id, pathogen_id, month)
        
        if signoff and signoff.status == SignoffStatus.APPROVED.value:
            return True
        
        return False
