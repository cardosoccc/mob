use std::collections::BTreeMap;

use k8s_openapi::api::core::v1::{
    Container, ContainerPort, EnvFromSource, EnvVar, EnvVarSource, HTTPGetAction, Pod, PodSpec,
    Probe, ResourceRequirements, SecretEnvSource,
};
use k8s_openapi::apimachinery::pkg::util::intstr::IntOrString;
use k8s_openapi::apimachinery::pkg::api::resource::Quantity;
use k8s_openapi::apimachinery::pkg::apis::meta::v1::ObjectMeta;
use kube::Resource;

use crate::crd::Session;
use crate::error::Error;

/// Build a Pod manifest for the given Session CR.
///
/// The pod has an owner reference back to the CR so Kubernetes garbage-collects
/// the pod when the CR is deleted.
pub fn build_agent_pod(ar: &Session) -> Result<Pod, Error> {
    let spec = &ar.spec;
    let run_name = ar
        .meta()
        .name
        .as_deref()
        .ok_or(Error::MissingObjectKey("metadata.name"))?;
    let ns = ar.meta().namespace.clone();
    let pod_name = format!("mob-agent-{run_name}");

    let mut env = vec![
        EnvVar {
            name: "SESSION_ID".into(),
            value: Some(run_name.to_string()),
            ..Default::default()
        },
        EnvVar {
            name: "AGENT_NAME".into(),
            value: Some(spec.agent_name.clone()),
            ..Default::default()
        },
    ];

    if let Some(sp) = &spec.system_prompt {
        env.push(EnvVar {
            name: "AGENT_SYSTEM_PROMPT".into(),
            value: Some(sp.clone()),
            ..Default::default()
        });
    }
    if let Some(me) = &spec.model_endpoint {
        env.push(EnvVar {
            name: "MODEL_ENDPOINT".into(),
            value: Some(me.clone()),
            ..Default::default()
        });
    }

    // Downward API: inject pod name and namespace so the agent can self-annotate
    env.push(EnvVar {
        name: "AGENT_POD_NAME".into(),
        value_from: Some(EnvVarSource {
            field_ref: Some(k8s_openapi::api::core::v1::ObjectFieldSelector {
                field_path: "metadata.name".into(),
                ..Default::default()
            }),
            ..Default::default()
        }),
        ..Default::default()
    });
    env.push(EnvVar {
        name: "AGENT_NAMESPACE".into(),
        value_from: Some(EnvVarSource {
            field_ref: Some(k8s_openapi::api::core::v1::ObjectFieldSelector {
                field_path: "metadata.namespace".into(),
                ..Default::default()
            }),
            ..Default::default()
        }),
        ..Default::default()
    });

    let oref = ar
        .controller_owner_ref(&())
        .ok_or(Error::MissingObjectKey("controller_owner_ref"))?;

    Ok(Pod {
        metadata: ObjectMeta {
            name: Some(pod_name),
            namespace: ns,
            owner_references: Some(vec![oref]),
            labels: Some(BTreeMap::from([
                ("app".to_string(), "mob-agent".to_string()),
                ("mob.io/session".to_string(), run_name.to_string()),
                ("mob.io/agent-name".to_string(), spec.agent_name.clone()),
            ])),
            ..Default::default()
        },
        spec: Some(PodSpec {
            containers: vec![Container {
                name: "agent".into(),
                image: Some(spec.agent_template.clone()),
                image_pull_policy: Some("IfNotPresent".into()),
                env: Some(env),
                env_from: Some(vec![EnvFromSource {
                    secret_ref: Some(SecretEnvSource {
                        name: "mob-agent-secrets".into(),
                        optional: Some(true),
                    }),
                    ..Default::default()
                }]),
                ports: Some(vec![ContainerPort {
                    container_port: 8081,
                    name: Some("agent-http".into()),
                    ..Default::default()
                }]),
                readiness_probe: Some(Probe {
                    http_get: Some(HTTPGetAction {
                        path: Some("/health".into()),
                        port: IntOrString::Int(8081),
                        ..Default::default()
                    }),
                    initial_delay_seconds: Some(3),
                    period_seconds: Some(5),
                    ..Default::default()
                }),
                resources: Some(ResourceRequirements {
                    requests: Some(BTreeMap::from([
                        ("cpu".to_string(), Quantity("100m".to_string())),
                        ("memory".to_string(), Quantity("256Mi".to_string())),
                    ])),
                    limits: Some(BTreeMap::from([
                        ("cpu".to_string(), Quantity("1000m".to_string())),
                        ("memory".to_string(), Quantity("1Gi".to_string())),
                    ])),
                    ..Default::default()
                }),
                ..Default::default()
            }],
            service_account_name: Some("mob-agent".into()),
            restart_policy: Some("Never".into()),
            ..Default::default()
        }),
        ..Default::default()
    })
}

/// Derive the Session state from the Kubernetes pod's status.
///
/// Priority:
/// 1. Pod annotation `mob.io/agent-state` (set by agent process for Idle/Busy)
/// 2. Pod `.status.phase` (Kubernetes-managed)
pub fn derive_state_from_pod(pod: &Pod) -> &str {
    // Check pod annotations for agent-reported state
    if let Some(annotations) = &pod.metadata.annotations {
        if let Some(agent_state) = annotations.get("mob.io/agent-state") {
            match agent_state.as_str() {
                "busy" => return "Busy",
                "idle" => return "Idle",
                "finished" => return "Finished",
                "failed" => return "Failed",
                _ => {}
            }
        }
    }

    // Fall back to pod phase
    let phase = pod
        .status
        .as_ref()
        .and_then(|s| s.phase.as_deref())
        .unwrap_or("Unknown");

    match phase {
        "Pending" => "Starting",
        "Running" => {
            let ready = pod
                .status
                .as_ref()
                .and_then(|s| s.container_statuses.as_ref())
                .map(|cs| cs.iter().all(|c| c.ready))
                .unwrap_or(false);
            if ready {
                "Idle"
            } else {
                "Starting"
            }
        }
        "Succeeded" => "Finished",
        "Failed" => "Failed",
        _ => "Starting",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use k8s_openapi::api::core::v1::{ContainerStatus, PodStatus};

    fn make_pod(phase: &str, ready: bool, annotations: Option<BTreeMap<String, String>>) -> Pod {
        Pod {
            metadata: ObjectMeta {
                annotations,
                ..Default::default()
            },
            status: Some(PodStatus {
                phase: Some(phase.to_string()),
                container_statuses: Some(vec![ContainerStatus {
                    ready,
                    name: "agent".to_string(),
                    image: "test:latest".to_string(),
                    image_id: String::new(),
                    restart_count: 0,
                    ..Default::default()
                }]),
                ..Default::default()
            }),
            ..Default::default()
        }
    }

    #[test]
    fn test_derive_state_pending_phase() {
        let pod = make_pod("Pending", false, None);
        assert_eq!(derive_state_from_pod(&pod), "Starting");
    }

    #[test]
    fn test_derive_state_running_not_ready() {
        let pod = make_pod("Running", false, None);
        assert_eq!(derive_state_from_pod(&pod), "Starting");
    }

    #[test]
    fn test_derive_state_running_ready() {
        let pod = make_pod("Running", true, None);
        assert_eq!(derive_state_from_pod(&pod), "Idle");
    }

    #[test]
    fn test_derive_state_succeeded() {
        let pod = make_pod("Succeeded", false, None);
        assert_eq!(derive_state_from_pod(&pod), "Finished");
    }

    #[test]
    fn test_derive_state_failed() {
        let pod = make_pod("Failed", false, None);
        assert_eq!(derive_state_from_pod(&pod), "Failed");
    }

    #[test]
    fn test_derive_state_annotation_busy_overrides_phase() {
        let annotations = BTreeMap::from([("mob.io/agent-state".to_string(), "busy".to_string())]);
        let pod = make_pod("Running", true, Some(annotations));
        assert_eq!(derive_state_from_pod(&pod), "Busy");
    }

    #[test]
    fn test_derive_state_annotation_idle() {
        let annotations = BTreeMap::from([("mob.io/agent-state".to_string(), "idle".to_string())]);
        let pod = make_pod("Running", true, Some(annotations));
        assert_eq!(derive_state_from_pod(&pod), "Idle");
    }

    #[test]
    fn test_derive_state_annotation_finished() {
        let annotations =
            BTreeMap::from([("mob.io/agent-state".to_string(), "finished".to_string())]);
        let pod = make_pod("Running", true, Some(annotations));
        assert_eq!(derive_state_from_pod(&pod), "Finished");
    }

    #[test]
    fn test_derive_state_annotation_failed() {
        let annotations =
            BTreeMap::from([("mob.io/agent-state".to_string(), "failed".to_string())]);
        let pod = make_pod("Running", true, Some(annotations));
        assert_eq!(derive_state_from_pod(&pod), "Failed");
    }

    #[test]
    fn test_derive_state_unknown_annotation_falls_through() {
        let annotations =
            BTreeMap::from([("mob.io/agent-state".to_string(), "unknown".to_string())]);
        let pod = make_pod("Running", true, Some(annotations));
        assert_eq!(derive_state_from_pod(&pod), "Idle");
    }

    #[test]
    fn test_derive_state_no_status() {
        let pod = Pod {
            metadata: ObjectMeta::default(),
            status: None,
            ..Default::default()
        };
        assert_eq!(derive_state_from_pod(&pod), "Starting");
    }

    #[test]
    fn test_build_agent_pod_basic() {
        use crate::crd::SessionSpec;

        let mut ar = Session::new(
            "test-run",
            SessionSpec {
                agent_id: "agent-123".into(),
                agent_name: "test-agent".into(),
                agent_template: "python:3.11".into(),
                system_prompt: Some("You are a test".into()),
                model_endpoint: None,
                task_id: None,
            },
        );
        // controller_owner_ref requires uid to be set
        ar.metadata.uid = Some("test-uid-1234".into());

        let pod = build_agent_pod(&ar).unwrap();
        let meta = &pod.metadata;

        assert_eq!(meta.name.as_deref(), Some("mob-agent-test-run"));
        assert!(meta.owner_references.as_ref().unwrap().len() == 1);

        let labels = meta.labels.as_ref().unwrap();
        assert_eq!(labels.get("app").unwrap(), "mob-agent");
        assert_eq!(labels.get("mob.io/session").unwrap(), "test-run");

        let container = &pod.spec.as_ref().unwrap().containers[0];
        assert_eq!(container.image.as_deref(), Some("python:3.11"));

        let env_names: Vec<&str> = container
            .env
            .as_ref()
            .unwrap()
            .iter()
            .map(|e| e.name.as_str())
            .collect();
        assert!(env_names.contains(&"SESSION_ID"));
        assert!(env_names.contains(&"AGENT_NAME"));
        assert!(env_names.contains(&"AGENT_SYSTEM_PROMPT"));
        assert!(!env_names.contains(&"MODEL_ENDPOINT"));
    }
}
