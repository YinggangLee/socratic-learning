# Building Effective Agents

> 原文：https://www.anthropic.com/engineering/building-effective-agents
> 作者：Erik S. and Barry Zhang (Anthropic)

---

We've worked with dozens of teams building LLM agents across industries. Consistently, the most successful implementations use simple, composable patterns rather than complex frameworks.

Over the past year, we've worked with dozens of teams building large language model (LLM) agents across industries. Consistently, the most successful implementations weren't using complex frameworks or specialized libraries. Instead, they were building with simple, composable patterns.

## What Are Agents?

"Agent" can be defined in several ways. Some customers define agents as fully autonomous systems that operate independently over extended periods, using various tools to accomplish complex tasks. Others use the term to describe more prescriptive implementations that follow predefined workflows. At Anthropic, we categorize all these variations as **agentic systems**, but draw an important architectural distinction between **workflows** and **agents**:

- **Workflows**: systems where LLMs and tools are orchestrated through predefined code paths.
- **Agents**: systems where LLMs dynamically direct their own processes and tool usage, maintaining control over how they accomplish tasks.

## When (and When Not) to Use Agents

When building applications with LLMs, we recommend finding the simplest solution possible, and only increasing complexity when needed. This might mean not building agentic systems at all. Agentic systems often trade latency and cost for better task performance, and you should consider when this tradeoff makes sense.

When more complexity is warranted, workflows offer predictability and consistency for well-defined tasks, whereas agents are the better option when flexibility and model-driven decision-making are needed at scale. For many applications, however, optimizing single LLM calls with retrieval and in-context examples is usually enough.

## When and How to Use Frameworks

There are many frameworks that make agentic systems easier to implement, including:

- LangChain's LangGraph
- Amazon Bedrock's AI Agent framework
- Rivet, a drag and drop GUI LLM workflow builder
- Vellum, another GUI tool for building and testing complex workflows
- Strands Agents SDK by AWS

These frameworks make it easy to get started by simplifying standard low-level tasks like calling LLMs, defining and parsing tools, and chaining calls together. However, they often create extra layers of abstraction that can obscure the underlying prompts and responses, making them harder to debug. They can also make it tempting to add complexity when a simpler setup would suffice.

**We suggest that developers start by using LLM APIs directly**: many patterns can be implemented in a few lines of code. If you do use a framework, ensure you understand the underlying code. Incorrect assumptions about what's under the hood are a common source of customer error.

## Building Blocks, Workflows, and Agents

### Building Block: The Augmented LLM

The basic building block of agentic systems is an LLM enhanced with augmentations such as retrieval, tools, and memory. Our current models can actively use these capabilities—generating their own search queries, selecting appropriate tools, and determining what information to retain.

We recommend focusing on two key aspects of the implementation: tailoring these capabilities to your specific use case and ensuring they provide an easy, well-documented interface for your LLM. One approach is through the **Model Context Protocol (MCP)**, which allows developers to integrate with a growing ecosystem of third-party tools.

### Workflow: Prompt Chaining

Prompt chaining decomposes a task into a sequence of steps, where each LLM call processes the output of the previous one. You can add programmatic checks ("gates") on any intermediate steps to ensure that the process is still on track.

**When to use**: Ideal for situations where the task can be easily and cleanly decomposed into fixed subtasks. The main goal is to trade off latency for higher accuracy, by making each LLM call an easier task.

**Examples**:
- Generating marketing copy, then translating it into a different language.
- Writing an outline of a document, checking that the outline meets certain criteria, then writing the document based on the outline.

### Workflow: Routing

Routing classifies an input and directs it to a specialized followup task. This workflow allows for separation of concerns, and building more specialized prompts. Without this workflow, optimizing for one kind of input can hurt performance on other inputs.

**When to use**: Works well for complex tasks where there are distinct categories that are better handled separately, and where classification can be handled accurately.

**Examples**:
- Directing different types of customer service queries (general questions, refund requests, technical support) into different downstream processes.
- Routing easy/common questions to smaller, cost-efficient models like Claude Haiku and hard/unusual questions to more capable models like Claude Sonnet.

### Workflow: Parallelization

LLMs can sometimes work simultaneously on a task and have their outputs aggregated programmatically. This manifests in two key variations:
- **Sectioning**: Breaking a task into independent subtasks run in parallel.
- **Voting**: Running the same task multiple times to get diverse outputs.

**When to use**: Effective when divided subtasks can be parallelized for speed, or when multiple perspectives or attempts are needed for higher confidence results.

**Examples**:
- Implementing guardrails where one model instance processes user queries while another screens them for inappropriate content.
- Automating evals for evaluating LLM performance, where each LLM call evaluates a different aspect.
- Reviewing code for vulnerabilities, where several different prompts review and flag the code.
- Evaluating content appropriateness with multiple prompts evaluating different aspects.

### Workflow: Orchestrator-Workers

In the orchestrator-workers workflow, a central LLM dynamically breaks down tasks, delegates them to worker LLMs, and synthesizes their results.

**When to use**: Well-suited for complex tasks where you can't predict the subtasks needed. The key difference from parallelization is flexibility—subtasks aren't pre-defined, but determined by the orchestrator based on the specific input.

**Examples**:
- Coding products that make complex changes to multiple files each time.
- Search tasks that involve gathering and analyzing information from multiple sources.

### Workflow: Evaluator-Optimizer

In the evaluator-optimizer workflow, one LLM call generates a response while another provides evaluation and feedback in a loop.

**When to use**: Particularly effective when we have clear evaluation criteria, and when iterative refinement provides measurable value. The two signs of good fit are: LLM responses can be demonstrably improved when a human articulates their feedback; and the LLM can provide such feedback.

**Examples**:
- Literary translation where nuances might be missed initially, but an evaluator LLM can provide useful critiques.
- Complex search tasks that require multiple rounds of searching and analysis.

## Agents

Agents are emerging in production as LLMs mature in key capabilities—understanding complex inputs, engaging in reasoning and planning, using tools reliably, and recovering from errors. Agents begin their work with either a command from, or interactive discussion with, the human user. Once the task is clear, agents plan and operate independently, potentially returning to the human for further information or judgement.

During execution, it's crucial for the agents to gain "ground truth" from the environment at each step (such as tool call results or code execution) to assess progress. Agents can then pause for human feedback at checkpoints or when encountering blockers. The task often terminates upon completion, but it's also common to include stopping conditions (such as a maximum number of iterations) to maintain control.

Agents can handle sophisticated tasks, but their implementation is often straightforward. They are typically just LLMs using tools based on environmental feedback in a loop. It is therefore crucial to design toolsets and their documentation clearly and thoughtfully.

**When to use**: Agents can be used for open-ended problems where it's difficult or impossible to predict the required number of steps, and where you can't hardcode a fixed path. The LLM will potentially operate for many turns, and you must have some level of trust in its decision-making.

**Tradeoffs**: The autonomous nature of agents means higher costs, and the potential for compounding errors. Extensive testing in sandboxed environments, along with appropriate guardrails, is recommended.

**Examples**:
- A coding agent to resolve GitHub issues (SWE-bench), which involve edits to many files based on a task description.
- Claude's "computer use" reference implementation, where Claude uses a computer to accomplish tasks.

## Combining and Customizing These Patterns

These building blocks aren't prescriptive. They're common patterns that developers can shape and combine to fit different use cases. The key to success is measuring performance and iterating on implementations. **Only add complexity when it demonstrably improves outcomes.**

Success in the LLM space isn't about building the most sophisticated system. It's about building the **right** system for your needs. Start with simple prompts, optimize them with comprehensive evaluation, and add multi-step agentic systems only when simpler solutions fall short.

## Three Core Principles for Agents

When implementing agents, we try to follow three core principles:

1. **Simplicity** in your agent's design.
2. **Transparency** by explicitly showing the agent's planning steps.
3. **Carefully craft your agent-computer interface (ACI)** through thorough tool documentation and testing.

Frameworks can help you get started quickly, but don't hesitate to reduce abstraction layers and build with basic components as you move to production. By following these principles, you can create agents that are not only powerful but also reliable, maintainable, and trusted by their users.

---

## Appendix 1: Agents in Practice

### Customer Support
Customer support combines familiar chatbot interfaces with enhanced capabilities through tool integration. This is a natural fit for more open-ended agents because:
- Support interactions naturally follow a conversation flow while requiring access to external information and actions.
- Tools can be integrated to pull customer data, order history, and knowledge base articles.
- Actions such as issuing refunds or updating tickets can be handled programmatically.
- Success can be clearly measured through user-defined resolutions.

### Software Development (Coding Agents)
The software development space has shown remarkable potential for LLM features, with capabilities evolving from code completion to autonomous problem-solving. Agents are particularly effective because:
- Code solutions are verifiable through automated tests.
- Agents can iterate on solutions using test results as feedback.
- The problem space is well-defined and structured.
- Output quality can be measured objectively.

---

## Appendix 2: Prompt Engineering Your Tools

No matter which agentic system you're building, tools will likely be an important part of your agent. **Tools** enable Claude to interact with external services and APIs by specifying their exact structure and definition in the API. When Claude responds, it will include a **tool_use block** in the API response if it plans to invoke a tool. Tool definitions and specifications should be given just as much prompt engineering attention as your overall prompts.

### Tool Format Design Principles

1. **Give the model enough tokens to "think"** before it writes itself into a corner.
2. **Keep the format close to what the model has seen naturally** occurring in text on the internet.
3. **Make sure there's no formatting "overhead"** such as having to keep an accurate count of thousands of lines of code, or string-escaping any code it writes.

### ACI (Agent-Computer Interface) Design

One rule of thumb is to think about how much effort goes into human-computer interfaces (HCI), and plan to invest just as much effort in creating good **agent**-computer interfaces (ACI):

- **Put yourself in the model's shoes.** Is it obvious how to use this tool, based on the description and parameters?
- **How can you change parameter names or descriptions to make things more obvious?** Think of this as writing a great docstring for a junior developer on your team.
- **Test how the model uses your tools.** Run many example inputs to see what mistakes the model makes, and iterate.
- **Poka-yoke your tools.** Change the arguments so that it is harder to make mistakes.

**Example from Anthropic's SWE-bench agent**: They spent more time optimizing tools than the overall prompt. They found that the model would make mistakes with tools using relative filepaths after the agent had moved out of the root directory. To fix this, they changed the tool to always require absolute filepaths—and the model used this method flawlessly.
