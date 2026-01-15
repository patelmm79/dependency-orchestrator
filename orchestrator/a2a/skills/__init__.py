"""
A2A Skills for Dependency Orchestrator
"""
from orchestrator.a2a.skills.receive_change_notification import ReceiveChangeNotificationSkill
from orchestrator.a2a.skills.get_impact_analysis import GetImpactAnalysisSkill
from orchestrator.a2a.skills.get_dependencies import GetDependenciesSkill
from orchestrator.a2a.skills.add_dependency_relationship import AddDependencyRelationshipSkill

__all__ = [
    'ReceiveChangeNotificationSkill',
    'GetImpactAnalysisSkill',
    'GetDependenciesSkill',
    'AddDependencyRelationshipSkill',
]
