## overview

- mob is a tool for orchestrating ai agents
- open-source and cloud-native
- cloud provider agnostic
- built on top of kubernetes+postgres
- can be run locally with kind+sqlite, or any combination of k8s+db
- designed to be multitenant
- can be used for personal use-cases, for running multiple agents, or enterprise level use cases, with tons of agents from multiple domains running in paralllel, coordinating work between each other
- composed by a cli interface that interacts with a rest api

## domain model

- agent
	- the definition of the agent, stored in the database;
	- have a common yaml representation;
	- have a system prompt;
	- have an agent template, which is a docker image stored in some docker registry;
	- the agent template can be a field with the image address in the registry;
	- have a set of predefined skills;
	- have a set of mcp servers (mcp servers features won't be included in the first version);
	- have a model endpoint, which defines the model api that should be called. this should be made using the litellm sdk, pointing to a litellm gateway;
	

- agent template
	- the docker image of some kind of agent;
	- agents developed with different types of languages and frameworks should have different docker images;
	- the docker image should define an agent developed with some technology, adapting the agent yaml definition to the technology used in the template;
	- initially, a template using pydantic ai should be developed;
	- there isn't a separate table/entity for agent templates, is just an attribute of the agent;

- agent run
	- represents the instantiation of an agent;
	- effectively is a pod running on kubernetes with the containerized agent;
	- can be in one of the following states:
	- pending (scheduled, but not yet running);
	- starting (bootstraping, initializing, but not ready to receive instructions)
	- idle (fully initialized, waiting for instructions);
	- busy (working, not available to work on a new task immediately);
	- finished (completed the task/instruction with success);
	- failed (terminated with some error, or could not meet the definition of done by some reason)

- model endpoint (can be implemented in a later version)
	- a litellm proxy model endpoint
	- should represent the llm endpoints used by the agents;
	- should abstract llm interactions;

- task
	- an instruction that is given to some agent;
	- have a definition of done, which is a condition that should be met to consider the agent run as sucessful;

- user
	- an user of the system
	- have an email, which is the username

- organization
	- being multitenant, it can exist multiple organizations using the tool;
	- have a name;
	- have an unique string identifier, manually defined when the organization is created;

- domain
	- a division inside an organization;
	- resources as agents, model apis, etc., can be related to a specific domain in organization;
	- every organization have a "default" domain, which is created when an organization is created;
	- have a name;
	- have a unique string identifier, which the suffix is created when the domain isccreated, and the prefix being the identifier of the organization. say i have an organization "foo" and a domain "bar", the identifier will be "foo-bar";

- group
	- an specific group of users inside an organization;
	- used for defining group-level resources access;
	- when a domain is created, there is a respective group that is created too;
	- users can be added and removed from groups;
	- it isn't clear if is needed to create a group table in the application, or keycloak would handle it all;

- role
	- a specific role that can be attached to a user or a group;
	- a role is composed by a set of permissions;
	- it seems that is not needed to have the role explictly in the application,  and it can be handled by keycloak;

- skills
	- are capabilities that the llm can execute;
	- it folllows the anthropic's skills specification;
	- agents can have skills, but skills can exist even without agents;
	- should be a skill registry to agents use it;
	- skills have a name;
	- have a description;
	- have a SKILLS.md
	- have references (a references folder with specific instructions and scripts);

## cli commands

- mob orgs (list organizations)
- mob org
	- create (create an organization)
	- edit (edit an organization)
	- delete (delete an organization)
	- show (show details of an organization)
- mob domains (list domains)
- mob domain
	- create (create a domain)
	- edit (edit a domain)
	- delete (delete a domain)
	- show (show details of a domain)
- mob users (list users)
- mob user
	- create (create an user)
	- edit (edit an user)
	- delete (delete an user)
	- show (show details of an user)
	- grant (grant access to a resource)
	- revoke (revoke access to a resource)
- mob groups (list groups)
- mob group
	- create (create a group)
	- edit (edit a group)
	- delete (delete a group)
	- show (show details of a group)
- mob agents (list agents)
- mob agent
	- create (create an agent)
	- edit (edit an agent)
	- delete (delete an agent)
	- show (show details of an agent)
	- run (run an instance of an agent)
	- stop (stop an instance of an agent)
	- logs (show the logs of an agent)
	- attach (attach to the pod af an agent)
	- send (send a message to the agent)
- mob skills (list skills)
- mob skill
	- create (create a skill)
	- edit (edit a skill)
	- delete (delete a skill)
- mob configs (list configs)
- mob config
	- set (set a config value)
	- get (get a config value)

## tech stack

- python + click for the cli
- python + fastapi for the rest api
- kubernetes
- postgres/sqlite with sqlalchemy
- keycloak for authentication / authorization / identity provider
- kubernetes-native crds for agents, agentruns and modelapis, built with kube-rs;

## tecnical considerations

- for maintaining the state of AgentRuns should be used a kubernetes-native controller, developed with kube-rs to avoid having to use some external solution to keep track of agent executions;
- user table should be adapted to keycloak's needs
- local configurations should be stored in ~/.mob/config.json
- use uv to manage environments and dependencies

## observations

- create and implement test scenarios for every cli command;
- create unit tests and integration tests that tests end-to-end (cli -> rest api -> database k8s);
- use kind to run tests that involve k8s;
- use flat pytest tests functions to create python tests, don't create test classes;
- implement every requested feature and don't stop before assuring it is everything working

## references

- [skills](https://agentskills.io/home)
