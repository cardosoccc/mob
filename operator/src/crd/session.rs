use std::collections::BTreeMap;

use kube::CustomResource;
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// Spec for a Session custom resource.
/// The Python API writes .spec; the operator writes .status.
#[derive(CustomResource, Serialize, Deserialize, Default, Debug, Clone, JsonSchema)]
#[kube(
    group = "mob.io",
    version = "v1",
    kind = "Session",
    namespaced,
    status = "SessionStatus",
    shortname = "sess",
    printcolumn = r#"{"name":"State","type":"string","jsonPath":".status.state"}"#,
    printcolumn = r#"{"name":"Agent","type":"string","jsonPath":".spec.agentName"}"#,
    printcolumn = r#"{"name":"Pod","type":"string","jsonPath":".status.podName"}"#
)]
pub struct SessionSpec {
    /// ID of the agent in the mob database.
    #[serde(rename = "agentId")]
    pub agent_id: String,

    /// Human-readable agent name.
    #[serde(rename = "agentName")]
    pub agent_name: String,

    /// Docker image to run as the agent pod.
    #[serde(rename = "agentTemplate")]
    pub agent_template: String,

    /// System prompt injected as AGENT_SYSTEM_PROMPT env var.
    #[serde(rename = "systemPrompt", default, skip_serializing_if = "Option::is_none")]
    pub system_prompt: Option<String>,

    /// Model endpoint URL injected as MODEL_ENDPOINT env var.
    #[serde(rename = "modelEndpoint", default, skip_serializing_if = "Option::is_none")]
    pub model_endpoint: Option<String>,

    /// Optional task ID to associate with this session.
    #[serde(rename = "taskId", default, skip_serializing_if = "Option::is_none")]
    pub task_id: Option<String>,

    /// Additional environment variables to inject into the agent pod.
    #[serde(rename = "envVars", default, skip_serializing_if = "Option::is_none")]
    pub env_vars: Option<BTreeMap<String, String>>,
}

/// Status written by the operator to reflect observed pod state.
#[derive(Deserialize, Serialize, Clone, Debug, Default, JsonSchema)]
pub struct SessionStatus {
    /// Current state: Pending, Starting, Idle, Busy, Finished, Failed.
    pub state: String,

    /// Name of the Kubernetes pod running this agent.
    #[serde(rename = "podName", default, skip_serializing_if = "Option::is_none")]
    pub pod_name: Option<String>,

    /// Error message if the session failed.
    #[serde(rename = "errorMessage", default, skip_serializing_if = "Option::is_none")]
    pub error_message: Option<String>,

    /// ISO 8601 timestamp of the last state transition.
    #[serde(rename = "lastTransitionTime", default, skip_serializing_if = "Option::is_none")]
    pub last_transition_time: Option<String>,
}
