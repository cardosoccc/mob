use std::sync::Arc;
use std::time::Duration;

use k8s_openapi::api::core::v1::Pod;
use kube::api::{Api, Patch, PatchParams};
use kube::runtime::controller::Action;
use kube::runtime::finalizer::{finalizer, Event};
use kube::{Client, ResourceExt};

use crate::crd::{AgentRun, AgentRunStatus};
use crate::error::{Error, Result};
use crate::resources::pod::{build_agent_pod, derive_state_from_pod};

/// Finalizer name for the AgentRun CR.
pub const FINALIZER: &str = "mob.io/agent-run-cleanup";

/// Shared context for the controller.
pub struct Context {
    pub client: Client,
}

/// Top-level reconcile function — delegates to finalizer handler.
pub async fn reconcile(ar: Arc<AgentRun>, ctx: Arc<Context>) -> Result<Action> {
    let ns = ar.namespace().unwrap_or_default();
    let name = ar.name_any();
    let run_api: Api<AgentRun> = Api::namespaced(ctx.client.clone(), &ns);

    tracing::info!(name = %name, ns = %ns, "reconciling AgentRun");

    finalizer(&run_api, FINALIZER, ar, |event| async {
        match event {
            Event::Apply(ar) => reconcile_apply(ar, ctx.clone()).await,
            Event::Cleanup(ar) => reconcile_cleanup(ar, ctx.clone()).await,
        }
    })
    .await
    .map_err(|e| Error::Finalizer(Box::new(e)))
}

/// Error policy: requeue after 60 seconds on failure.
pub fn error_policy(_ar: Arc<AgentRun>, error: &Error, _ctx: Arc<Context>) -> Action {
    tracing::error!(%error, "reconcile failed, requeuing");
    Action::requeue(Duration::from_secs(60))
}

/// Apply reconciliation — create pods, sync state.
async fn reconcile_apply(ar: Arc<AgentRun>, ctx: Arc<Context>) -> Result<Action> {
    let ns = ar.namespace().unwrap_or_default();
    let name = ar.name_any();
    let run_api: Api<AgentRun> = Api::namespaced(ctx.client.clone(), &ns);
    let pod_api: Api<Pod> = Api::namespaced(ctx.client.clone(), &ns);

    let state = ar
        .status
        .as_ref()
        .map(|s| s.state.as_str())
        .unwrap_or("Pending");

    let pod_name = format!("mob-agent-{name}");

    match state {
        "Pending" => {
            // Create the agent pod using server-side apply (idempotent)
            let pod = build_agent_pod(&ar)?;
            pod_api
                .patch(
                    &pod_name,
                    &PatchParams::apply("mob-operator"),
                    &Patch::Apply(&pod),
                )
                .await
                .map_err(Error::Kube)?;

            tracing::info!(name = %name, pod = %pod_name, "created agent pod");

            update_status(&run_api, &name, "Starting", Some(&pod_name), None).await?;
        }

        "Starting" => {
            match pod_api.get_opt(&pod_name).await.map_err(Error::Kube)? {
                Some(pod) => {
                    let derived = derive_state_from_pod(&pod);
                    if derived != "Starting" {
                        tracing::info!(name = %name, state = %derived, "pod ready, transitioning");
                        update_status(&run_api, &name, derived, Some(&pod_name), None).await?;
                    }
                }
                None => {
                    tracing::warn!(name = %name, "pod not found during Starting");
                    update_status(
                        &run_api,
                        &name,
                        "Failed",
                        None,
                        Some("Pod not found"),
                    )
                    .await?;
                }
            }
        }

        "Idle" | "Busy" => {
            match pod_api.get_opt(&pod_name).await.map_err(Error::Kube)? {
                Some(pod) => {
                    let derived = derive_state_from_pod(&pod);
                    if derived != state {
                        tracing::info!(name = %name, from = %state, to = %derived, "state transition");
                        update_status(&run_api, &name, derived, Some(&pod_name), None).await?;
                    }
                }
                None => {
                    tracing::warn!(name = %name, "pod disappeared");
                    update_status(
                        &run_api,
                        &name,
                        "Failed",
                        None,
                        Some("Pod disappeared unexpectedly"),
                    )
                    .await?;
                }
            }
        }

        "Finished" | "Failed" => {
            // Terminal state — clean up pod if it still exists
            if let Ok(Some(_)) = pod_api.get_opt(&pod_name).await {
                tracing::info!(name = %name, pod = %pod_name, "cleaning up pod for terminal run");
                let _ = pod_api
                    .delete(&pod_name, &Default::default())
                    .await;
            }
            return Ok(Action::await_change());
        }

        _ => {
            tracing::warn!(name = %name, state = %state, "unknown state");
        }
    }

    // Requeue every 15 seconds for active runs
    Ok(Action::requeue(Duration::from_secs(15)))
}

/// Cleanup on CR deletion — delete the pod.
async fn reconcile_cleanup(ar: Arc<AgentRun>, ctx: Arc<Context>) -> Result<Action> {
    let ns = ar.namespace().unwrap_or_default();
    let name = ar.name_any();
    let pod_api: Api<Pod> = Api::namespaced(ctx.client.clone(), &ns);
    let pod_name = format!("mob-agent-{name}");

    tracing::info!(name = %name, "cleaning up AgentRun");

    if let Ok(Some(_)) = pod_api.get_opt(&pod_name).await {
        tracing::info!(pod = %pod_name, "deleting agent pod");
        let _ = pod_api.delete(&pod_name, &Default::default()).await;
    }

    Ok(Action::await_change())
}

/// Update the AgentRun CR status subresource.
async fn update_status(
    api: &Api<AgentRun>,
    name: &str,
    state: &str,
    pod_name: Option<&str>,
    error_message: Option<&str>,
) -> Result<()> {
    let now = chrono::Utc::now().to_rfc3339();

    let status = serde_json::json!({
        "apiVersion": "mob.io/v1",
        "kind": "AgentRun",
        "status": AgentRunStatus {
            state: state.to_string(),
            pod_name: pod_name.map(|s| s.to_string()),
            error_message: error_message.map(|s| s.to_string()),
            last_transition_time: Some(now),
        }
    });

    api.patch_status(name, &PatchParams::apply("mob-operator"), &Patch::Apply(status))
        .await
        .map_err(Error::Kube)?;

    Ok(())
}
