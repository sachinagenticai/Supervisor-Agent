from supervisor_control_tower.tools.base import ToolRegistry
from supervisor_control_tower.tools.finops import FinOpsOptimizationTool
from supervisor_control_tower.tools.infrastructure import InfrastructureProvisioningTool
from supervisor_control_tower.tools.pipeline import PipelineTroubleshootingTool
from supervisor_control_tower.tools.project_management import ProjectManagementTool


def build_tool_registry() -> ToolRegistry:
    return ToolRegistry([
        PipelineTroubleshootingTool(),
        InfrastructureProvisioningTool(),
        FinOpsOptimizationTool(),
        ProjectManagementTool(),
    ])

__all__ = ["build_tool_registry", "ToolRegistry"]
