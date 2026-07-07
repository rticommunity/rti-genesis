# MONTHLY RESEARCH AND DEVELOPMENT (R&D) PHASE II TECHNICAL STATUS REPORT

**AFX246-DPCSO1: Open Topic**

**A Data-Centric Distributed Agentic Framework for DAF Simulation**

---

**Contract Information:** | **Controlling Office:**
--------------------------|-------------------------
**Topic Number:** AFX246-DPCSO1 | AF Ventures Execution Team
**Contract Number:** FA864924P0974 | Allen Kurella, Contracting Officer
**Phase:** II (Base Period) | **Email:** P2@afwerx.af.mil
**Status Report No.:** 2 (Bi-Monthly) |
**Period of Performance:** 14 AUGUST 2024 – 18 MAY 2026 |

---

**Principal Investigator:** | **TPOC:**
-------------------------|-----------
**Name:** Dr. Jason Upchurch | **Name:** Mr. Kevin Kelly, AFLCMC/HBE
**Email:** jason@rti.com | **Email:** kevin.kelly.34@us.af.mil

---

**Contractor:**
- **Name:** Real-Time Innovations, Inc.
- **Phone:** 408-990-7400
- **Address:** 232 East Java, Sunnyvale, CA. 94089

---

**Report Authors:**
Jason Upchurch, Gianpiero Napoli, Paul Pazandak

---

**SBIR/STTR DATA RIGHTS:**
Expiration of SBIR Data Rights: 14-AUGUST-2044. The Government's rights to use, modify, reproduce, release, perform, display, or disclose technical data or computer software marked with this legend are restricted during the period shown as provided in paragraph (b)(5) of the Rights In Other Than Commercial Technical Data and Computer Software—Small Business Innovation Research (SBIR) Program clause contained in the above identified contract. After the expiration date shown above, the Government has perpetual government purpose rights as provided in paragraph (b)(5) of that clause. Any reproduction of technical data, computer software, or portions thereof marked with this legend must also reproduce the markings.

**DISTRIBUTION STATEMENT B:** Distribution authorized to U.S. Government Agencies Only: Proprietary Information (18-NOV-2024) DFARS SBIR/STTR data rights - DFARS 252.227-7018

---

## TABLE OF CONTENTS

1.  **PROGRAMMATIC INFORMATION**
    1.1 Problem Description
    1.2 The Opportunity
    1.3 Brief Description of RTI's Core Technology
2.  **PHASE II EFFORT**
    2.1 High-Level Summary
    2.2 Research Objectives
3.  **PHASE II WORK PLAN OUTLINE**
    3.1 Tasking
    3.2 Schedule
4.  **TASK STATUS UPDATES**
    4.1 Task 1: Requirements and Metrics Capture
    4.2 Task 2: Driving Simulation Use Case Down-Select, Definition, and Functional Decomposition
    4.3 Task 3: Early Prototype Refinement
    4.4 Task 4: Inter-agent Library Design & Implementation, Demonstration
    4.5 Task 5: Simulink/MATLAB Use Case Integration
    4.6 Task 6: Architecture Refinement, Security Access and Dataflow
    4.7 Task 7: Agent Service Registry Design, Implementation, and Demonstration
    4.8 Task 8: Semantic Security Service Layer, Design, & Implementation
    4.9 Task 9: Multi-Agent Framework Library Development & Demonstration
    4.10 Task 10: Documentation
5.  **APPENDICES (TASK DETAILED UPDATES)**

---

## 1 Programmatic Information

### 1.1 Problem Description

The promise of generative AI and generative agents is very likely world changing and nowhere will this be seen more acutely than on the battlefield. AI agent augmentation in weapons platforms, training, information management, target recognition, intelligence analysis, and the myriads of other applications will be a necessary discriminator for the warfighter. Due to generative AI agent potential, PEO Digital and AFRL USAF CMSO are investing heavily in generative AI agents to interact with simulation systems. This ongoing work shows increasing promise due to the exponential performance gains in general LLMs and agent frameworks; however, they have identified several technology gaps to their goal of a "safe, secure, reliable" integration of generative AI agents into simulation environments. Beyond implementation specifics, DAF suffers the same integration hurdles that the larger commercial tech industry suffers from, which is integration of these independent generative agents into a cohesive framework integrated with a meaningful system, commonly called "completing the stack". In short, DAF has promising AI technologies that will be a force multiplier for the warfighter and a robust simulation environment; however, DAF lacks a "safe, secure, reliable" bridging stack to make it all work together. They require a standardized, stable, robust framework for AI agent interaction between agents, humans, and the target environment that allows for rapid deployment and integration of cutting-edge AI technologies.

Over the course of months of discussions with PEO Digital and USAF CMSO on this topic, we have identified the three challenges below and we frame them in PEO Digital's "safe, secure, and reliable" theme:

-   **C1. Safe:** Safety within a multi-agent framework is all about dealing with complexity. AI models and agents are largely non-deterministic and heavily rely on correct prompting to achieve desirable results. Generative AI prompting has become its own field to guide generative AI down the correct paths to success. Managing prompts (system and user), context, and the correct and limited delivery of this information will be a primary challenge in this project. Agent performance is a unique challenge to the generative AI problem set that seeks to achieve agent decision reliability through prompts, in-context learning, training, and machine learning. In a multi-agent environment, this contextual data must be made available synchronously for machine and in context learning, and asynchronously for model training.
-   **C2. Secure:** All current AI agent frameworks rely on basic security measures like wire encryption (if at all), which is insufficient for comprehensive security. Implementing advanced security capabilities, include authentication, encryptions, and access control is crucial, yet challenging due to the interconnected nature of distributed AI agents. To make matters more complex, AI models (and consequently their agents) can be socially engineered by manipulating prompts, system prompts, and any other in context messaging
-   **C3. Reliable:** Reliability challenges can be separated into three categories. Reliability in agent integration; reliability in messaging; and reliability system integration. The primary challenge in multi-agent interaction and integration lie in the fact there is no standard communication layer that exists between agent frameworks (and in some instances, within agent frameworks). These communication connections must currently be home grown and while narrow scope interactions between two agents is trivial, a fully distributed agentic framework is complex in the extreme. In the same light, messaging reliability in the simple context is trivial but becomes quit complex in a distributed system with multicast messages. Further, none of the challenges in system integration are likely to be trivial and are currently the significant hurdle for even "one-off" agents to become useful.

### 1.2 The Opportunity

In response to the challenges encountered by PEO Digital and AFRL USAF CMSO in their effort to bring generative AI to warfighter training & operational use, we propose to build a Data-Centric Distributed Agentic Framework called **GENESIS: Gen-AI Network for Enhanced Simulation Integration and Security** (see Figure 1).

_Figure 1: GENESIS will help unleash the power of generative AI for warfighter training and operational use cases._

We identified the following set of high-level requirements that, if addressed, will enable the design and development of a safe, secure, reliable, and interoperable AI agent framework. They form the basis of our proposal to design and develop the GENESIS framework.

-   **R1. Safe:** GENESIS will require semantic level monitoring sufficient to use data for future training and/or in-context learning for system repeatability, correction, and safety. This data must be available for access both synchronously and asynchronously.
-   **R2. Secure:** GENESIS will require agent and interface level access control. This access control must be authenticated with industry standard security mechanisms and used to maintain secure during message transit. Further, GENESIS must also employ semantic security to prevent unintentional or malicious misbehaviors unique to generative AI agents.
-   **R3. Reliable:** GENESIS will require a standardized, open communication layer for agent-to-agent and agent-to-human communication with supporting integrations into common agent frameworks (Semantic Kernel, LangChain), AI programming languages (Python, C#, Javascript), and model inference endpoints (HTTPS). This communication layer must be robust, scale, and preferably tested in relevant environments. Finally, GENESIS must integrate with Simulink during the Phase II with a target integration with AFSIM in post Phase II follow on efforts. Within the timeframe and funding of the Phase II effort, our objective is to address each of these requirements though the design and implementation of a generative, multi-agent communication framework that is safe, secure, and reliable by using an industry leading, robust communication framework that is battletested in more than 1,400 DoD applications.

### 1.3 Brief Description of RTI's Core Technology

Real-Time Innovations, Inc. (RTI) is a commercial software vendor. We develop a secure, real-time communications high assurance framework for both industrial and defense systems. RTI Connext DDS is a set of developer tools, a software library that is compiled into an application, and additional runtime services that enhance its use; it provides all of the distributed communications services needed within any system. RTI Connext DDS developer licenses, support, and services accounts for most of RTI's revenue – approximately $50M in 2023. Our customers buy RTI Connext DDS because it provides all of the distributed communications needs for their small to extremely large critical distributed systems. It is scalable, secure, robust, proven, and promotes MOSA. It enables them to build their systems using less code and more modularity, substantially reducing the cost of their systems.

Connext DDS implements the OMG DDS standard. The standard ensures that all compliant products are interoperable at both the wire level and API level. This means that applications built by different teams using various competing vendor products will all interoperate with very little effort. RTI Connext DDS is in over 1,700 commercial applications and 600 research programs, including: NASA's KSC launch system, simulators, autonomous/electric commercial vehicles, ground stations, aircraft, ships, satellites, medical devices, power utilities, and many other mission-critical systems. It has also been used as the foundation for HWIL simulation and testing for both ground and airborne vehicles (e.g, Volkswagen, Passaro/Airbus). Key to this effort, DDS provides access control/security, self-discovery, years of operational deployment in critical systems, scales to incredibly large environments, and is an open standard with both open source and many commercial implementations.

In the following discussion, we describe the DDS standard in general, and not just our commercial product, which is fully DDS compliant. This also applies to other commercial implementations of DDS.

DDS is data centric – it treats data as a first-class citizen. Most other communications solutions are message centric and send their data over the network as opaque payloads that the network cannot understand. Only the applications themselves do because all of the knowledge about encoding and decoding the data rests with them. This forces every application to reinvent features for reliability, security, fault tolerance, scalability, and end to end interoperability.

In contrast, data centric means that developers naturally define open data models that describe the structure of the data that will move between applications. This allows DDS to automatically handle encoding, security, optimized/reliable delivery, and more. It also means that the government can own the interfaces, while the prime owns the implementation. DDS offers the government a real path to modular open system architectures (MOSA).

RTI Connext DDS is a loosely-coupled, and fully decentralized communications framework. This makes it possible to scale systems quickly, without recompiling or shutting the systems down. Instead of creating brittle, point-to-point network dependencies, DDS communicates over the concept of topics. Applications simply declare what kind of data (topics) they are interested in and DDS delivers it. This eliminates the brittleness of requiring endpoints to identify their communications peers – DDS handles all of this via a dynamic discovery handshake process, so developers can focus on application code rather than reinventing how to send data over the network.

DDS provides fine-grained read/write access control to the data. While encrypting all communications is generally useful when a system only wants to restrict subsets of the data this approach will not work. Using DDS fine-grained access control guarantees that only authorized applications receive this data – enabling highly customizable multi-level secure communications. This is software-defined security.

Finally, the loosely coupled nature of DDS and its use of topics to communicate both support location-independent processing. This promotes system modularity and resilience, a key benefit of MOSA system design.

---

## 2 Phase II Effort

### 2.1 High-Level Summary

RTI brings two major non-defense commercial solutions to this proposal. First is our TRL-9 Connext product, which is an interoperable implementation of the OMG DDS standard in use in 1,440 DoD applications as well as supported by Simulink/MATLAB, the target environment identified by PEO Digital. Second is our TRL-2 distributed generative AI framework, based on the DDS standard, which was used as a feasibility study to derisk the use of DDS as a communication framework for inter-agent communication. We currently do not have competition – our solution is a unified framework that will facilitate the integration of, and interaction between, existing agent frameworks.

_Figure 2: GENESIS will provide Full Stack Multi-Agent Simulation Integration – it will enable DAF systems to rapidly reap the potential from dynamically interacting AI agents. GENESIS is an open-standards, modular, secure, and reliable framework that will make it possible to quickly integrate AI agents from many contractors and other sources._

### 2.2 Research Objectives

Our goal in Phase II is to design, develop, demonstrate, and deliver a fully functioning GENESIS product baseline with end-to-end capabilities, including supporting the integration of AI agents in the MATLAB/Simulink simulation environment (AFSIM integration is targeted for post-Phase II). As discussed above, we are extending our TRL-9 distributed communications framework, RTI Connext DDS –the following five objectives address the capability gaps that are needed for the implementation of the GENESIS distributed agent framework features:

**Objective 1: Develop Comprehensive State Monitoring and Interaction**
Achieve comprehensive state monitoring and semantic-level interaction among AI agents using the Object Management Group Data Distribution Service (OMG DDS) and RTI Connext DDS.
*Key Results:*
-   Develop and validate tools for semantic analysis of agent interactions, measured by the system's ability to accurately interpret and analyze the context of communications.
-   Implement logging and review mechanisms for agent interactions, with success measured by the system's ability to provide a complete and accessible audit trail.
-   Demonstrate real-time monitoring capabilities in a test environment, achieving 100% accuracy in detecting and reporting agent states.

**Objective 2: Develop Multi-faceted Security Environment**
Enhance the security of AI agent interactions through a multi-faceted security environment leveraging RTI Connext DDS's existing security mechanisms and additional semantic controls.
*Key Results:*
-   Implement fine-grained access control policies and validate their effectiveness in restricting data and service access to authorized agents only.
-   Integrate semantic controls to monitor the content of communications, with success measured by the reduction of inappropriate or harmful (inadvertent or malicious) interactions as detected by the system.

**Objective 3: Develop Seamless Integration with MATLAB/Simulink Simulation Environment**
Develop a seamless integration of the distributed AI framework with MATLAB/Simulink, with a transition plan for follow-on integration with AFSIM.
*Key Results:*
-   Successfully implement and test the MATLAB/Simulink plug-in, measured by the seamless execution of complex scenarios involving AI agents and Simulink models.
-   Demonstrate the interoperability between AI agents and simulation models in MATLAB/Simulink, achieving 100% successful integration in test cases.
-   Complete the initial integration plan for AFSIM, with sign-off from AFSIM stakeholders.

**Objective 4: Develop a Collaborative AI Environment**
Create a collaborative AI environment that mirrors a human workplace (agents can discover and request services from authorized agents, humans, or data), enabling dynamic and effective interaction among AI agents.
*Key Results:*
-   Implement the DDS-based communication framework and measure its effectiveness in facilitating real-time data exchange between agents, achieving 100% message delivery.
-   Develop tools that enable collaborative task planning, execution, and evaluation, with success measured by agents' improved performance on complex tasks.
-   Ensure seamless data sharing between agents, with success measured by the accessibility and relevance of shared information in collaborative scenarios.

**Objective 5: Develop and Demonstrate Inter-Agent Library**
Develop libraries for direct communication over DDS in Python, C#, and JavaScript, ensuring seamless interoperability between AI agents developed using different frameworks and technologies.
*Key Results:*
-   Develop and validate communication libraries for Python, C#, and JavaScript, achieving seamless inter-agent communication.
-   Conduct 3 or more demonstrations during Phase II to stakeholders and potential customers, gathering feedback and achieving sign-off on the functionality and performance of the libraries.
-   Validate (via operational testing) that the libraries support direct communication over DDS, adhering to the DDS standard and QoS policies.

---

## 3 Phase II Work Plan Outline

### 3.1 Tasking

In order to accomplish our proposed objectives, we have defined the following tasks:

**Task 1: Requirements and Metrics Capture (months 1-2)**
*Objective:* Gather detailed requirements and define key performance indicators (KPIs) for the project.
-   Task 1.1: Conduct workshops and meetings with stakeholders to gather detailed requirements.
-   Task 1.2: Define key performance indicators (KPIs) and metrics for the project.
-   Task 1.3: Document requirements and metrics for future reference and validation.
*Outcomes:* A comprehensive set of requirements and defined KPIs, providing a clear foundation for the project's development and evaluation.

**Task 2: Driving Simulation Use Case Down-Select, Definition, and Functional Decomposition (months 3-4)**
*Objective:* Identify and evaluate potential simulation use cases and define them in detail.
-   Task 2.1: Identify and evaluate potential simulation use cases for the implementation of the Distributed AI Framework in the MATLAB environment.
-   Task 2.2: Select the most relevant and impactful use cases for further development.
-   Task 2.3: Define the selected use cases in detail, including functional requirements and expected outcomes.
-   Task 2.4: Decompose the system into functional components to guide development and integrations.
*Outcomes:* A detailed definition and functional decomposition of the selected simulation use cases, ensuring clarity and direction for subsequent development tasks.

**Task 3: Early Prototype Refinement (months 5-6)**
*Objective:* Refine the early prototype architecture and address any technology gaps.
-   Task 3.1: Evaluate the approach of our early work on distributed AI agents for technology gaps in the base framework.
-   Task 3.2: Conduct a data modeling analysis for basic messaging structures and methods for inter-agent communication and discovery.
-   Task 3.3: Refine the early prototype architecture to enable the development of advanced features of the framework.
-   Task 3.4: Implement the basic framework to provide inter-agent communication over DDS.
*Outcomes:* A refined prototype that addresses identified technology gaps and supports inter-agent communication.

**Task 4: Inter-agent Library Design & Implementation, Demonstration (months 7-10)**
*Objective:* Develop and demonstrate the initial inter-agent communication library.
-   Task 4.1: Select initial library language and agent framework for the first demonstration based on customer feedback.
-   Task 4.2: Implement the initial library based on the target architecture.
-   Task 4.3: Prepare and conduct a demonstration of the initial architecture to stakeholders, gathering feedback for further refinement.
*Outcomes:* A functional inter-agent communication library demonstrated to stakeholders, providing a basis for further refinement.

**Task 5: Simulink/MATLAB Use Case Integration (months 11-12)**
*Objective:* Integrate the distributed AI framework with MATLAB/Simulink and plan for AFSIM integration.
-   Task 5.1: Work with stakeholders to ensure that targeted use cases are still highly relevant.
-   Task 5.2: Refine the architecture based on feedback from demonstrations to stakeholders.
-   Task 5.3: Architect the use case with the refined distributed AI agent architecture.
-   Task 5.4: Design and implement any needed agents for the targeted use cases within the Simulink/MATLAB environment.
*Outcomes:* Successful integration of AI agents with MATLAB/Simulink, with a plan for subsequent AFSIM integration.

**Task 6: Architecture Refinement, Security Access and Dataflow (months 13-14)**
*Objective:* Enhance the security and dataflow aspects of the framework.
-   Task 6.1: Analyze data flow of the demo architecture for threat modeling using STRIDE.
-   Task 6.2: Analyze access requirements for the security layer using STRIDE threat modeling.
-   Task 6.3: Implement an access model using DDS Security.
*Outcomes:* A robust security model ensuring safe and secure inter-agent communication and dataflow.

**Task 7: Agent Service Registry Design, Implementation, and Demonstration (months 15-16)**
*Objective:* Develop and demonstrate the agent service registry.
-   Task 7.1: Analyze and select target agent frameworks based on state-of-the-art agent frameworks in the market.
-   Task 7.2: Evaluate any changes to mechanisms and messaging requirements for inter-agent communication between heterogeneous frameworks.
-   Task 7.3: Architect an agent service registry into the distributed AI agent framework.
-   Task 7.4: Prepare and conduct a demonstration of the current architecture within the driving use case to stakeholders, gathering feedback for further refinement.
*Outcomes:* A functional agent service registry demonstrated to stakeholders, facilitating inter-agent communication across diverse frameworks.

**Task 8: Semantic Security Service Layer, Design, & Implementation (months 17-18)**
*Objective:* Develop a semantic security layer to enhance interaction safety.
-   Task 8.1: Refine architecture based on feedback from stakeholders.
-   Task 8.2: Evaluate semantic security requirements based on STRIDE and error states.
-   Task 8.3: Design and implement a semantic security agent targeting input/output evaluations.
-   Task 8.4: Incorporate semantic security evaluations into endpoint library architecture and agent service registry.
*Outcomes:* A semantic security layer integrated into the framework, enhancing the safety and reliability of AI agent interactions.

**Task 9: Multi-Agent Framework Library Development & Demonstration (months 12, 21)**
*Objective:* Develop and demonstrate communication libraries for multiple agent frameworks.
-   Task 9.1: Work with stakeholders to ensure that targeted agent frameworks for inter-agent communication are still relevant.
-   Task 9.2: Implement final library for target agent framework #1.
-   Task 9.3: Implement final library for target agent framework #2.
-   Task 9.4: Implement final library for target agent framework #3.
*Outcomes:* Completed communication libraries for multiple agent frameworks, demonstrated and validated through stakeholder feedback.

**Task 10: Documentation**
*Objective:* Create comprehensive documentation for the distributed agent framework and libraries.
-   Task 10.1: Create documentation for the distributed agent framework, including security and agent registry.
-   Task 10.2: Create documentation for agent framework library integration for target agent framework #1.
-   Task 10.3: Create documentation for agent framework library integration for target agent framework #2.
-   Task 10.4: Create documentation for agent framework library integration for target agent framework #3.
*Outcomes:* Comprehensive documentation that supports the deployment, integration, and usage of the distributed agent framework and communication libraries.

**Task 11. Project Management.** We will utilize standard project management practices to coordinate the oversight and successful execution of this project. We will engage with the AFRL USAF CMSO, PEO Digital, and MathWorks, setting up a tempo for interaction within the first month of execution. We will manage the timely delivery of reports, updates, and milestones. We will also manage requirements gathering for the subsequent tasks.
*Outcomes:* Reports and overall successful progress against schedule/milestones/deliverables.

**Agile Practices:** Where applicable, we will use agile spiral-based development practices, and share documentation and test results. This iterative approach will ensure continuous improvement and stakeholder engagement throughout the project.

## 4 Task Status Updates

This section documents the activity that has taken place over the course of the execution of each milestone. It is not intended to be cumulative. The following subsections are broken down by the ten high-level tasks described above.

### Overall Progress

**Project Management Summary.** On Schedule

During this reporting period (months 5-6), the team focused on **Task 3: Early Prototype Refinement**. This involved a detailed evaluation of the initial broker-based prototype, analysis of core data models, refinement of the architecture based on initial findings, and implementation of the refined basic framework components. The key deliverables for this milestone, the Revised Prototype Architecture document and the Data-Model Analysis Report, were completed and submitted.

**Accomplishments**
-   **Completion of Task 3.1:** Evaluated the initial broker-based prototype (described in `docs/early_prototype_documentation.md`), identifying strengths (dynamic registration, ID-based routing) and areas for refinement, particularly around function invocation patterns and potential registry bottlenecks.
-   **Completion of Task 3.2:** Conducted and documented a detailed data modeling analysis for the core messaging structures used in the broker-based architecture, including registration, function discovery, and basic agent-interface communication.
-   **Completion of Task 3.3:** Refined the initial prototype architecture, proposing clearer patterns for function invocation via the registry and refining the dynamic topic naming conventions. Documented in the Revised Prototype Architecture deliverable.
-   **Completion of Task 3.4:** Implemented the refined basic framework components based on the revised architecture, focusing on the `ServiceRegistry` and foundational DDS topic/listener patterns for the broker model.

**Status Summary**
Task 3 was completed successfully within the planned timeframe (months 5-6). The refinement activities provided valuable insights into the broker-based approach, solidifying the core registration and discovery mechanisms while also highlighting areas for future consideration regarding scalability and the complexity of function invocation through a central broker. The project remains on schedule as per the `MileStoneTable.md`.

**Subcontract Management.** None

### Task 3: Early Prototype Refinement

**Status:** Completed

**Introduction**
Task 3 focused on evaluating and refining the initial GENESIS prototype, which utilized a broker-based architecture centered around a `ServiceRegistry`. The goal was to solidify the foundational components and identify necessary improvements before developing more complex features like inter-agent libraries and specific use-case integrations. 

The process was divided into four sequential activities:
-   **Prototype Evaluation (Task 3.1):** Assessing the initial implementation for technology gaps and areas needing improvement within the broker model.
-   **Data Modeling Analysis (Task 3.2):** Analyzing and documenting the DDS data structures required for core framework communication (registration, discovery, basic messaging).
-   **Architecture Refinement (Task 3.3):** Revising the broker-based architecture based on the evaluation findings, focusing on clarity, robustness, and defining patterns for upcoming features like function invocation.
-   **Basic Framework Implementation (Task 3.4):** Implementing the refined architectural concepts into the core framework code, particularly the `ServiceRegistry` and supporting DDS utilities.

By completing Task 3, the project solidified the design and implementation of the core broker-based framework, producing key architectural documentation and a refined codebase ready for the next stage of development (Task 4: Inter-agent Library).

#### Task 3.1: Evaluate the approach of our early work on distributed AI agents for technology gaps in the base framework.

**Overview**
The team conducted a thorough review of the initial prototype code (`service.py`, example usage) and documentation (`early_prototype_documentation.md`, `Architecture-Detailed.md`). The evaluation focused on the effectiveness of the broker-based approach for dynamic registration, discovery, and basic communication using DDS.

**Evaluation Findings**
-   **Strengths:**
    -   The core mechanism of using a central `ServiceRegistry` for assigning unique IDs proved effective for dynamic component registration.
    -   The convention of using these IDs for dynamic topic naming (`QuestionTopic-{target_id}`, `AnswerTopic-{source_id}`) successfully enabled targeted communication without prior knowledge of network addresses.
    -   The DDS-based function discovery mechanism (querying the registry) was functional and met the basic requirement for agents to find capabilities.
-   **Areas for Refinement / Gaps Identified:**
    -   **Function Invocation Pattern:** While functions could be discovered, the *standardized pattern* for an agent to invoke a function through the registry or directly with the function provider needed explicit definition within the architecture. The early prototype outlined this but lacked a concrete implementation pattern.
    -   **Registry Scalability/Reliability:** The reliance on a single, centralized `ServiceRegistry` was identified as a potential bottleneck and single point of failure for larger-scale deployments. While acceptable for the prototype, this needed consideration for future robustness.
    -   **Error Handling:** Standardized error handling patterns (e.g., for registration failures, unavailable agents/functions, DDS communication timeouts) were missing from the initial framework implementation.
    -   **Complexity:** Managing the dynamic creation and cleanup of numerous DDS Topics, DataReaders, and DataWriters based on numeric IDs could become complex for application developers.

**Conclusion**
The evaluation confirmed the viability of the core broker-based concepts for the prototype stage but highlighted the need to define the function invocation pattern more clearly and address potential scalability/reliability concerns of the central registry in future iterations or alternative designs.

#### Task 3.2: Conduct a data modeling analysis for basic messaging structures and methods for inter-agent communication and discovery.

**Overview**
This task involved analyzing, refining, and formally documenting the DDS data types defined in `genesis_semantic_message.xml`. The focus was on ensuring these structures adequately supported the registration, discovery, and basic communication needs of the refined broker-based architecture.

**Analysis and Refinements**
-   **Registration Types:** (`genesis_agent_registration_announce`, `genesis_agent_registration_assign`, etc.) The existing types were deemed sufficient but documentation was added to clarify the role of each field, especially `prefered_name` vs. the assigned numeric ID, and the purpose of `default_capable` or `interface_type`.
-   **Function Discovery Types:** (`query_genesis_function_list`, `genesis_function_list_response`) The use of JSON within the DDS message for the function list was reviewed. While functional, the team noted potential benefits of using DDS sequences for more type safety in the future, but kept the JSON approach for the refined prototype for simplicity. The need for richer function metadata (e.g., input/output schemas) in the registration and discovery process was identified for future work.
-   **Basic Messaging Types:** (`genesis_semantic_msg`, `genesis_semantic_msg_answer`) These generic types were analyzed for their suitability for simple request/reply interactions between interfaces and agents. The analysis confirmed their basic utility but highlighted the need for more specific types or conventions for complex interactions, particularly function calls. Fields like `sessionID`, `series`, `source`, `target`, and `status` were validated as essential for managing conversations.
-   **Data Model Report:** A report was generated documenting the finalized DDS types for M3, their fields, intended usage within the broker architecture, and relationships between them.

**Conclusion**
The data modeling analysis solidified the core DDS message structures for the refined broker prototype. It ensured clarity on how components exchange registration information, discover functions, and perform basic communication, while also noting areas for future enhancement, particularly around function metadata and potentially moving away from generic JSON payloads.

#### Task 3.3: Refine the early prototype architecture to enable the development of advanced features of the framework.

**Overview**
Based on the findings from Task 3.1 and the analysis in Task 3.2, the team refined the broker-based architecture. The goal was to create a more robust and clearly defined foundation for subsequent tasks, especially Task 4 (Inter-agent Library).

**Architectural Refinements (Broker-Based)**
-   **Standardized Function Invocation Pattern (Defined):** A specific sequence and set of DDS topics were formally defined for how an agent should invoke a function discovered via the registry. This involved the agent sending a request to a standardized topic associated with the function's ID, and the function provider responding on a dynamic answer topic associated with the calling agent's ID, mirroring the existing question/answer pattern.
-   **Registry Responsibilities Clarified:** The role of the `ServiceRegistry` was strictly defined as handling registration, ID assignment, and function *discovery*. It was explicitly decided *not* to route function invocation traffic itself in the refined architecture to avoid becoming a bottleneck; instead, it provides the necessary information (function ID) for the agent to communicate *directly* with the function provider (using dynamically named topics).
-   **Error Reporting:** Basic conventions for using the `status` field in answer messages to indicate success, failure, or pending states were added to the architectural documentation.
-   **Dynamic Topic Management:** Best practices were documented for components regarding the creation, caching, and potential cleanup of dynamic DDS entities (Topics, Readers, Writers) associated with specific communication partners or functions.
-   **Revised Architecture Document:** The primary deliverable was an updated architecture document detailing these refinements, including sequence diagrams for registration, discovery, and the newly defined function invocation pattern within the broker model.

**Conclusion**
The architectural refinement resulted in a clearer, more formalized design for the broker-based prototype. By defining the function invocation pattern and clarifying the registry's role, the revised architecture provided a solid blueprint for the implementation work in Task 3.4 and the library development in Task 4. It also implicitly highlighted the increasing complexity of managing direct peer-to-peer DDS interactions, subtly paving the way for considering alternative architectures later.

#### Task 3.4: Implement the basic framework to provide inter-agent communication over DDS.

**Overview**
This task involved translating the refined architecture from Task 3.3 into code. The focus was on updating the `ServiceRegistry` implementation and creating basic utility functions or classes embodying the standardized patterns for registration, discovery, and communication (question/answer, basic function invocation) within the broker model.

**Implementation Details**
-   **Updated `ServiceRegistry` (`service.py`):**
    -   The registry logic was updated to handle registration requests (agent, interface, function) according to the refined data models and architectural patterns.
    -   The function discovery mechanism (`QueryFunctionListTopic` listener) was verified against the refined architecture.
    -   Internal data structures (`agent_registry`, `function_registry`) were maintained as described in `early_prototype_documentation.md`.
-   **DDS Utilities/Helpers:** Basic Python functions or classes were created to encapsulate common DDS operations according to the refined patterns:
    -   Registering an agent/interface/function and waiting for the ID assignment response.
    -   Querying the registry for the function list.
    -   Creating dynamic DDS Topics, DataReaders, and DataWriters based on target/source IDs.
    -   Sending a standard question message and listening for an answer using the dynamic topics.
    -   (Partial/Basic) Sending a function invocation request according to the newly defined pattern (Task 3.3) and listening for the response.
-   **Testing:** Basic tests were performed to ensure the refined `ServiceRegistry` and helper utilities functioned correctly for registration, discovery, and simple message exchange according to the revised architecture.

**Conclusion**
The implementation phase solidified the refined broker-based framework's core components. The updated `ServiceRegistry` and basic DDS utilities provided the necessary infrastructure and building blocks as defined in the revised architecture, making the framework ready for the development of the initial inter-agent library (Task 4). The implementation focused purely on the broker model defined in M3.

---

### 4.2 Task 1: Requirements and Metrics Capture

-   Task 1.1 Initial Stakeholder Engagement: **Complete**
-   Task 1.2 KPIs: **Complete**
-   Task 1.3 Metrics for Validation: **Complete**

### 4.3 Task 2: Driving Simulation Use Case Down-Select, Definition, and Functional Decomposition

-   Task 2.1: Engage with the TPOC on the target simulation/demo: **Complete**
-   Task 2.2: Down select the use case and demo environment: **Complete**
-   Task 2.3: Define the use cases in detail: **Complete**
-   Task 2.4: Function decomposition of the use cases: **Complete**.

### 4.4 Task 3: Early Prototype Refinement
**Status:** Completed (Details above)
-   Task 3.1: Evaluate the approach of our early work: **Complete**
-   Task 3.2: Conduct a data modeling analysis: **Complete**
-   Task 3.3: Refine the early prototype architecture: **Complete**
-   Task 3.4: Implement the basic framework: **Complete**

### 4.5 Task 4: Inter-agent Library Design & Implementation, Demonstration
**Status:** Not Started (Planned for months 7-10)
**Plans in the next 2-month period:**
-   Task 4.1: Down select the initial target library environment (e.g., Python).
-   Task 4.2: Begin implementation of the initial library based on the refined broker architecture (Task 3.3) and utilities (Task 3.4).

### 4.6 Task 5: Simulink/MATLAB Use Case Integration
**Status:** Not Started (Planned for months 11-12)
**Plans in the next 2-month period:**
-   N/A (Work begins after Task 4 demo)

### 4.7 Task 6: Architecture Refinement, Security Access and Dataflow
**Status:** Not Started (Planned for months 13-14)
**Plans in the next 2-month period:**
-   N/A

### 4.8 Task 7: Agent Service Registry Design, Implementation, and Demonstration
**Status:** In Progress (Planned completion: months 15-16)
**Current Progress:**
- Task 7.1 (Framework Target Analysis): **~50% Complete**
  - Completed initial analysis of agent framework requirements through broker-based prototype
  - Identified key registration and discovery patterns for agent frameworks
  - Further analysis needed for distributed architecture requirements

- Task 7.2 (Inter-agent Communication Requirements): **~50% Complete**
  - Analyzed and implemented basic messaging structures for registration and discovery
  - Established dynamic topic naming conventions for direct communication
  - Additional analysis needed for distributed registry architecture

- Task 7.3 (Service Registry Architecture): **~20% Complete**
  - Implemented initial broker-based `ServiceRegistry` with core functionality:
    - Dynamic component registration and ID assignment
    - Function cataloging and discovery
    - Basic relationship brokering between interfaces and agents
  - Future work needed for distributed architecture and enhanced security features

**Key Accomplishments:**
1. **Core Registry Implementation:**
   - Successfully implemented centralized registration for agents, interfaces, and functions
   - Developed unique ID assignment mechanism for runtime component identification
   - Created function discovery mechanism via `QueryFunctionListTopic`

2. **Data Model Development:**
   - Defined and implemented DDS types for registration announcements/assignments
   - Created standardized message structures for function discovery
   - Established dynamic topic naming conventions

3. **Basic Integration Patterns:**
   - Implemented registration workflows for agents and interfaces
   - Created function discovery and listing capabilities
   - Developed initial patterns for component relationship management

**Next Steps:**
1. Design and implement distributed registry architecture
2. Enhance security features for registry access
3. Develop more robust error handling and recovery mechanisms
4. Create comprehensive documentation for registry integration

**Plans in the next 2-month period:**
- Begin design work for distributed registry architecture
- Document lessons learned from broker-based implementation
- Engage with stakeholders on security requirements for distributed model

### 4.9 Task 8: Semantic Security Service Layer, Design, & Implementation
**Status:** Not Started (Planned for months 17-18)
**Plans in the next 2-month period:**
-   N/A

### 4.10 Task 9: Multi-Agent Framework Library Development & Demonstration
**Status:** Not Started (Planned for months 19-21)
**Plans in the next 2-month period:**
-   N/A

### 4.11 Task 10: Documentation
**Status:** Ongoing (Initial docs refined in Task 3, major updates planned towards end)
**Plans in the next 2-month period:**
-   Focus on documentation for Task 4 deliverables.

---

## 5 Appendices (Task Detailed Updates)

### Development - M3 (Months 5-6)

The development effort during Milestone 3 focused exclusively on refining the initial broker-based prototype described in `docs/early_prototype_documentation.md`. Key technical activities included:

1.  **Code Review and Analysis:** The existing Python code for the `ServiceRegistry` (`service.py`) and example agent/interface usage was analyzed against the architecture documentation. This identified inconsistencies and areas lacking clear patterns, particularly for function invocation.
2.  **Data Model Refinement (`genesis_semantic_message.xml`):** While no major changes were made to the structure definitions, the team clarified the intended use of each field within the context of the broker architecture. Documentation (`Data-Model Analysis Report`) was created to capture these clarifications. The use of JSON for the function list was retained for simplicity in this phase.
3.  **Architecture Revision:** Based on the evaluation, the architecture document was updated to formally define the interaction pattern for function invocation. This involved specifying that the agent, after discovering a function's ID from the registry, would construct a dynamic DDS topic (`FunctionTopic-{function_id}`) to send the request directly to the function provider, rather than routing the invocation through the registry itself. The response path (`FunctionAnswerTopic-{caller_id}`) was similarly defined for direct communication. This refinement aimed to prevent the registry from becoming a communication bottleneck for function calls. Sequence diagrams illustrating this refined flow were added to the `Revised Prototype Architecture` document.
4.  **Registry Implementation (`service.py` Update):** The Python implementation of the `ServiceRegistry` was updated to align with the refined (but still broker-based) architecture. Its core responsibilities remained registration, ID assignment, and function list publication. No function invocation *routing* logic was added, as per the refined design.
5.  **Basic DDS Helper Utilities:** Small Python helper functions were implemented to streamline common tasks for developers using the *refined broker framework*:
    *   `register_agent(name, description)`: Handles sending the announcement and waiting for the assigned ID.
    *   `discover_functions()`: Handles querying the registry and parsing the function list response.
    *   `create_communication_endpoints(own_id, target_id)`: Helper to create the necessary dynamic `QuestionTopic` writer and `AnswerTopic` reader.
    *   `send_request(writer, own_id, target_id, message)` / `listen_for_response(reader)`: Basic wrappers for the question/answer pattern.

These development activities resulted in a refined, documented, and tested version of the *broker-based* prototype, fulfilling the requirements of Milestone 3 and establishing the foundation for the Inter-agent Library development in Milestone 4. Identified limitations concerning registry scalability and error handling were noted for future consideration.

### Project Management / Stakeholder Development

Regular internal meetings were held to review progress on the prototype refinement and data modeling. The `Revised Prototype Architecture` and `Data-Model Analysis Report` were compiled and prepared for DAF review as per the M3 acceptance criteria. No significant issues impacting schedule arose during this period. Engagement continued with the TPOC regarding the upcoming demonstration planning for Task 4.

---

**END OF REPORT**


