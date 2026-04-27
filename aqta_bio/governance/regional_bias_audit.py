"""
Regional bias audit module for computing metrics per WHO region.

This module extends the bias audit functionality to compute performance
metrics separately for each WHO region represented in the validation set,
identifying geographic disparities in model performance.

Validates Requirements 2.1, 2.2, 2.3, 2.4.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from aqta_bio.backtesting.historical_events import BacktestResult, HistoricalSpillover


@dataclass
class RegionMetrics:
    """
    Performance metrics for a single WHO region.
    
    Attributes:
        region: WHO region identifier (AFRO, EURO, SEARO, AMRO, EMRO)
        recall: Recall (sensitivity) for the region
        precision: Precision for the region
        f1_score: F1 score for the region
        support: Number of events in the region
        tile_count: Number of tiles with predictions in the region
    """
    region: str
    recall: float
    precision: float
    f1_score: float
    support: int
    tile_count: int = 0


@dataclass
class RegionalBiasAuditResult:
    """
    Result of regional bias audit.
    
    Attributes:
        region_metrics: Dictionary mapping region IDs to RegionMetrics
        flagged_gap: Optional tuple of (low_region, high_region, gap_points)
            if a gap > 15 percentage points is detected
        overall_pass: Whether the audit passed (no flagged gaps)
        recommendations: List of recommendations for improving regional coverage
    """
    region_metrics: Dict[str, RegionMetrics]
    flagged_gap: Optional[Tuple[str, str, int]] = None
    overall_pass: bool = True
    recommendations: List[str] = None
    
    def __post_init__(self):
        if self.recommendations is None:
            self.recommendations = []


class RegionalBiasAudit:
    """
    Regional bias audit for computing performance metrics per WHO region.
    
    This class:
    1. Computes recall, precision, and F1 separately for each WHO region
    2. Flags any recall gap exceeding 15 percentage points between regions
    3. Generates recommendations for training data improvements
    
    Implements Requirements 2.1, 2.2, 2.3, 2.4.
    """
    
    def __init__(self, gap_threshold: float = 15.0):
        """
        Initialize regional bias audit.
        
        Args:
            gap_threshold: Percentage point gap threshold for flagging (default: 15)
        """
        self.gap_threshold = gap_threshold
    
    def compute_region_metrics(
        self,
        results: List[BacktestResult],
        spillovers: List[HistoricalSpillover],
    ) -> Dict[str, RegionMetrics]:
        """
        Compute per-region recall, precision, and F1 scores.
        
        Implements Requirement 2.1: Compute recall, precision, and F1
        separately for each WHO region.
        
        Args:
            results: List of BacktestResult objects from backtesting
            spillovers: List of HistoricalSpillover events
        
        Returns:
            Dictionary mapping region IDs to RegionMetrics
        """
        # Create lookup for spillover by event_id
        spillover_lookup = {s.event_id: s for s in spillovers}
        
        # Group results by region
        region_hits: Dict[str, List[bool]] = {}
        region_tiles: Dict[str, set] = {}
        
        for result in results:
            spillover = spillover_lookup.get(result.event_id)
            if spillover is None:
                continue
            
            region = spillover.tile_id.split("-")[0] if "-" in spillover.tile_id else "UNKNOWN"
            
            if region not in region_hits:
                region_hits[region] = []
                region_tiles[region] = set()
            
            region_hits[region].append(result.hit)
            region_tiles[region].add(spillover.tile_id)
        
        # Compute metrics for each region
        region_metrics = {}
        
        for region, hits in region_hits.items():
            n_total = len(hits)
            n_hits = sum(1 for h in hits if h)
            
            # Compute recall (sensitivity)
            recall = n_hits / n_total if n_total > 0 else 0.0
            
            # Compute precision (for backtesting, this is the proportion of
            # predicted hits that were actual hits)
            # In backtesting, we predict "hit" if max_risk_score >= threshold
            # Precision = TP / (TP + FP) where TP = hits, FP = misses
            n_misses = n_total - n_hits
            precision = n_hits / n_total if n_total > 0 else 0.0
            
            # Compute F1 score
            if precision + recall > 0:
                f1_score = 2 * precision * recall / (precision + recall)
            else:
                f1_score = 0.0
            
            region_metrics[region] = RegionMetrics(
                region=region,
                recall=recall,
                precision=precision,
                f1_score=f1_score,
                support=n_total,
                tile_count=len(region_tiles.get(region, set())),
            )
        
        return region_metrics
    
    def detect_flagged_gap(
        self,
        region_metrics: Dict[str, RegionMetrics],
    ) -> Optional[Tuple[str, str, int]]:
        """
        Detect if any region has a recall gap > 15 percentage points.
        
        Implements Requirement 2.2: Flag any recall gap exceeding 15
        percentage points between highest and lowest performing regions.
        
        Args:
            region_metrics: Dictionary mapping region IDs to RegionMetrics
        
        Returns:
            Tuple of (low_region, high_region, gap_points) if gap > threshold,
            None otherwise
        """
        if not region_metrics:
            return None
        
        # Find regions with highest and lowest recall
        regions_by_recall = sorted(
            region_metrics.items(),
            key=lambda x: x[1].recall
        )
        
        low_region, low_metrics = regions_by_recall[0]
        high_region, high_metrics = regions_by_recall[-1]
        
        # Compute gap in percentage points
        gap_points = int((high_metrics.recall - low_metrics.recall) * 100)
        
        # Check if gap exceeds threshold
        if gap_points > self.gap_threshold:
            return (low_region, high_region, gap_points)
        
        return None
    
    def generate_recommendation(
        self,
        flagged_gap: Tuple[str, str, int],
    ) -> str:
        """
        Generate recommendation for training data improvement.
        
        Implements Requirement 2.4: Generate recommendation identifying
        which regions need additional training data.
        
        Args:
            flagged_gap: Tuple of (low_region, high_region, gap_points)
        
        Returns:
            Recommendation string for training data improvement
        """
        low_region, high_region, gap_points = flagged_gap
        
        return (
            f"Training data imbalance detected: {low_region} region has "
            f"{gap_points} percentage points lower recall than {high_region}. "
            f"Recommend adding more training samples from {low_region} region "
            f"to improve model generalizability."
        )
    
    def run_audit(
        self,
        results: List[BacktestResult],
        spillovers: List[HistoricalSpillover],
    ) -> RegionalBiasAuditResult:
        """
        Run complete regional bias audit.
        
        Implements Requirement 2.3: Run audit and produce structured report
        including per-region metrics, tile counts, and pass/fail determination.
        
        Args:
            results: List of BacktestResult objects from backtesting
            spillovers: List of HistoricalSpillover events
        
        Returns:
            RegionalBiasAuditResult with metrics, gap detection, and recommendations
        """
        # Compute region metrics
        region_metrics = self.compute_region_metrics(results, spillovers)
        
        # Detect flagged gap
        flagged_gap = self.detect_flagged_gap(region_metrics)
        
        # Generate recommendations
        recommendations = []
        if flagged_gap:
            recommendations.append(self.generate_recommendation(flagged_gap))
        
        # Determine overall pass/fail
        overall_pass = flagged_gap is None
        
        return RegionalBiasAuditResult(
            region_metrics=region_metrics,
            flagged_gap=flagged_gap,
            overall_pass=overall_pass,
            recommendations=recommendations,
        )
