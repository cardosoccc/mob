use std::sync::Arc;

use futures::StreamExt;
use k8s_openapi::api::core::v1::Pod;
use k8s_openapi::apiextensions_apiserver::pkg::apis::apiextensions::v1::CustomResourceDefinition;
use kube::api::{Api, Patch, PatchParams};
use kube::runtime::controller::Config;
use kube::runtime::watcher;
use kube::runtime::Controller;
use kube::{Client, CustomResourceExt};

use mob_operator::controller::{error_policy, reconcile, Context};
use mob_operator::crd::AgentRun;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "mob_operator=info,kube=warn".into()),
        )
        .init();

    tracing::info!("mob-operator starting");

    let client = Client::try_default().await?;

    // Register the AgentRun CRD (idempotent via server-side apply)
    let crds: Api<CustomResourceDefinition> = Api::all(client.clone());
    crds.patch(
        "agentruns.mob.io",
        &PatchParams::apply("mob-operator").force(),
        &Patch::Apply(AgentRun::crd()),
    )
    .await?;
    tracing::info!("AgentRun CRD registered");

    // Set up the controller
    let agent_runs: Api<AgentRun> = Api::all(client.clone());
    let pods: Api<Pod> = Api::all(client.clone());

    let ctx = Arc::new(Context {
        client: client.clone(),
    });

    Controller::new(agent_runs, watcher::Config::default())
        .owns(pods, watcher::Config::default())
        .with_config(Config::default().concurrency(2))
        .shutdown_on_signal()
        .run(reconcile, error_policy, ctx)
        .for_each(|res| async move {
            match res {
                Ok(o) => tracing::info!("reconciled {:?}", o),
                Err(e) => tracing::error!("reconcile error: {:?}", e),
            }
        })
        .await;

    tracing::info!("mob-operator shutting down");
    Ok(())
}
