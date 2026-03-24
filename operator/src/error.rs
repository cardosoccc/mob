/// Operator error types.
#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("Kubernetes API error: {0}")]
    Kube(#[source] kube::Error),

    #[error("Finalizer error: {0}")]
    Finalizer(#[source] Box<kube::runtime::finalizer::Error<Error>>),

    #[error("Missing object key: {0}")]
    MissingObjectKey(&'static str),

    #[error("Serialization error: {0}")]
    Serialization(#[source] serde_json::Error),
}

pub type Result<T, E = Error> = std::result::Result<T, E>;
