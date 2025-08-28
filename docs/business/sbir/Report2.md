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

---

## 4 Task Status Updates

This section documents the activity that has taken place over the course of the execution of each milestone. It is not intended to be cumulative. The following subsections are broken down by the ten high-level tasks described above.

### Overall Progress

**Project Management Summary.** Ahead of Schedule

Significant progress has been made on Task 2: Driving Simulation Use Case Down-Select, Definition, and Functional Decomposition. Following our initial project kickoff with the TPOC, the team has successfully completed all components of Task 2. This includes identifying potential use cases, selecting the most impactful scenario, defining functional requirements, and decomposing the system into actionable components for development.

**Accomplishments**
-   **Completion of Task 2.1:** Conducted a comprehensive evaluation of simulation use cases, leveraging insights from the TPOC and prior GENESIS research to align the project's goals with high-impact scenarios.
-   **Completion of Task 2.2:** Selected the ATC and Aircraft Interaction Simulation as the primary use case, emphasizing its alignment with stakeholder priorities and technical feasibility.
-   **Completion of Task 2.3:** Defined the ATC and Aircraft Interaction Simulation in detail, including functional requirements, workflows, and expected outcomes.
-   **Completion of Task 2.4:** Decomposed the system into modular components, providing a clear roadmap for development and integration.

**Status Summary**
The project continues without any issues or red flags to report. Task 2 was completed ahead of schedule, positioning the project well for subsequent development and testing phases. The detailed planning and functional decomposition completed in Task 2 provide a solid foundation for executing and validating the selected use case.

**Subcontract Management.** None

### 4.1.1 Task 2: Driving Simulation Use Case Down-Select, Definition, and Functional Decomposition

**Status:** Completed

**Introduction**
Task 2 focused on identifying, evaluating, selecting, and detailing a simulation use case to guide the implementation of the Distributed AI Framework in the GENESIS environment. This task aimed to align the framework's capabilities with stakeholder priorities while ensuring technical feasibility and operational impact.

The process was divided into four sequential activities:
-   **Use Case Evaluation (Task 2.1):** Identifying high-impact simulation scenarios and assessing their relevance, technical feasibility, and operational impact.
-   **Use Case Selection (Task 2.2):** Selecting the most impactful use case based on stakeholder input and project objectives.
-   **Use Case Definition (Task 2.3):** Defining the selected use case in detail, including functional requirements and expected outcomes.
-   **Functional Decomposition (Task 2.4):** Breaking the selected use case into functional components to guide modular development and seamless integration.

Through a collaborative process involving the Technical Point of Contact (TPOC) and leveraging insights from prior GENESIS research efforts, the **ATC and Aircraft Interaction Simulation** was selected as the driving use case. This decision was based on its alignment with stakeholder goals, its relevance to the U.S. Air Force mission, and its ability to demonstrate GENESIS's capabilities in a domain-critical scenario.

**Scope of Task 2**
The overarching goal of Task 2 was to establish a clear, actionable pathway for implementing the ATC and Aircraft Interaction Simulation. This included:
-   Leveraging GENESIS's modular architecture and DDS-based communication capabilities.
-   Highlighting distributed agent collaboration and real-time command execution.
-   Setting a foundation for future extensions into more complex scenarios, such as multi-agent collaboration or UAV swarm operations.

By completing Task 2, the project now has a well-defined, actionable plan for developing the simulation in a modular and scalable manner.

#### Task 2.1: Identify and Evaluate Potential Simulation Use Cases for the Distributed AI Framework in MATLAB Environment

**Overview**
As part of Task 2.1, we conducted a comprehensive evaluation of potential simulation use cases to guide the implementation of the Distributed AI Framework. This task included identifying scenarios that leverage the framework's strengths in real-time distributed communication, agent collaboration, and simulation integration. A key component of this evaluation was a meeting with the Technical Point of Contact (TPOC), during which we discussed practical use cases and determined the scope and focus for future efforts.

**TPOC Meeting Insights**
During the meeting with the TPOC, the following key points were discussed:

1.  **Potential Use Cases:** Several high-impact scenarios were reviewed, including:
    -   Flight tower and aircraft interaction simulations.
    -   Distributed agent systems for mission planning and execution.
    -   Geospatial analytics and real-time collaborative environments.
2.  **MATLAB Simulink Integration:**
    -   MATLAB Simulink was identified as an essential component for algorithm development, control system validation, and data flow simulations.
    -   However, due to the limitations of Simulink's current DDS Blockset version (it supports the older Connext DDS 6.2) and Mathworks' older UAV simulation example application, it was agreed that Simulink would not serve as the initial simulation for real-time operations. The outdated version limits full compatibility with the more advanced Connext DDS 7.x used by GENESIS.
    -   Simulink will instead function as a complementary module within the broader simulation ecosystem, focusing on isolated functional testing and algorithm validation.

**Evaluation of Use Cases**
The evaluation focused on aligning potential use cases with the following criteria:
-   **Relevance to Stakeholder Goals:**
    -   Emphasis on scenarios that demonstrate the GENESIS framework's distributed and modular nature.
-   **Technical Feasibility:**
    -   Consideration of tools and technologies currently available to GENESIS due to previous work with DDS integration (e.g., Connext Databus Simulation Unification, Unreal Engine, Unity).
-   **Operational Impact:**
    -   Use cases were assessed for their potential to showcase inter-agent collaboration and real-time communication.

**Initial Findings**
-   **Flight Tower and Aircraft Interaction:**
    -   This use case was deemed the most practical and impactful for initial development. It focuses on simulating ATC tower-to-aircraft communication and command validation.
    -   The TPOC emphasized this as the driving simulation to demonstrate GENESIS's capabilities in distributed agent communication.
-   **Distributed Agent Mission Planning:**
    -   Collaboration between multiple agents in a distributed system was identified as a secondary priority. It offers significant potential for demonstrating GENESIS's scalability.
-   **Visualization Tools and Coordinated Aerial Search:**
    -   Integrations with simulated drones for aerial search for optimized mission planning was discussed and remains interesting; however, this is a more long term application of what GENESIS enables through inter-agent communication.

**MATLAB Simulink as a Component**
While MATLAB Simulink's strengths in algorithm testing and simulation design are clear, its role in this project will be as a supportive component rather than a central driver. Its current limitations in DDS Blockset support prevent its direct integration into the GENESIS framework for real-time operations. Instead, Simulink will focus on:
-   Developing and validating specific subsystems (e.g., autopilot algorithms) from other research efforts.
-   Supporting isolated, scenario-based testing with exportable results to the broader GENESIS environment.
-   We are happy to work with Mathworks to resolve this limitation.

**Conclusion**
The evaluation phase of Task 2.1 has identified and prioritized the Flight Tower and Aircraft Interaction simulation as the primary use case. This simulation highlights GENESIS's distributed communication capabilities while leveraging Simulink for targeted algorithm testing. These insights will inform the selection and detailed definition of use cases in Task 2.2 and Task 2.3.

#### Task 2.2: Select the Most Relevant and Impactful Use Cases for Further Development

**Overview**
Building on the comprehensive evaluation conducted in Task 2.1, the selection of use cases focused on identifying scenarios that align closely with the project's objectives and stakeholder priorities. After detailed discussions with the TPOC and consideration of technical feasibility and operational impact, the **ATC and Aircraft Interaction Simulation** was selected as the primary use case for further development.

**Rationale for Use Case Selection**
1.  **Alignment with Stakeholder Goals:**
    -   The ATC and Aircraft Interaction Simulation directly supports the TPOC's vision of demonstrating GENESIS's capabilities in managing distributed communication between agents in real-time.
    -   This use case is highly relevant to the US Air Force's mission and will demonstrate GENESIS functionality in a domain DAF members understand.
    -   This use case showcases the core strengths of GENESIS, including agent collaboration, real-time command execution, and message handling.
2.  **Technical Feasibility:**
    -   Existing tools and frameworks, such as the Connext Databus used in simulation and agent models developed during previous IRAD GENESIS efforts, provide a strong foundation for this use case.
    -   The simplicity of using an autopilot system for aircraft control allows the focus to remain on agent communication and interaction protocols rather than complex flight dynamics.
3.  **Operational Impact:**
    -   This use case emphasizes real-world scenarios, such as issuing clearances, providing navigation instructions, and monitoring aircraft compliance. These are critical capabilities for distributed AI frameworks in aviation and defense environments.
    -   Real-time interaction between agents (e.g., ATC tower and aircraft) highlights GENESIS's flexibility for managing dynamic systems.

**Description of the Selected Use Case**
The ATC and Aircraft Interaction Simulation involves:
1.  **Simulating Realistic Communication:**
    -   The ATC agent issues commands (e.g., takeoff clearance, heading adjustments).
    -   The aircraft agent acknowledges and executes commands using an autopilot system.
2.  **Real-Time Monitoring and Logging:**
    -   State data such as heading, altitude, and speed are synchronized between agents and visualized for monitoring.
    -   All interactions are logged to support after-action review and system evaluation.
3.  **Leveraging GENESIS:**
    -   GENESIS coordinates communication between the ATC and aircraft agents.
    -   The framework manages agent registration, message passing, and error handling.

**Secondary Use Cases (Deferred for Later Phases)**
While the ATC and Aircraft Interaction Simulation was selected for immediate development, additional use cases identified in Task 2.1 remain valuable for future iterations:
-   **Distributed Agent Mission Planning:**
    -   Focuses on multi-agent collaboration for complex scenarios such as UAV swarm operations or search-and-rescue missions.
-   **Coordinated Aerial Search:**
    -   Explores the integration of geospatial visualization tools with simulated drones for optimized mission execution.

**Conclusion**
The ATC and Aircraft Interaction Simulation stands out as the most relevant and impactful use case for further development, aligning with the TPOC's priorities and the project's technical objectives. Its selection will enable GENESIS to demonstrate its strengths in distributed communication, laying the groundwork for more complex simulations in subsequent phases. Tasks 2.3 and 2.4 will further define and decompose this use case to guide implementation and integration.

#### Task 2.3: Define the Selected Use Case in Detail, Including Functional Requirements and Expected Outcomes

**Overview**
The selected use case, **ATC and Aircraft Interaction Simulation**, focuses on simulating the interaction between an air traffic control (ATC) tower and an aircraft. The goal is to validate GENESIS's capabilities in real-time agent communication, command handling, and state synchronization. This simulation will highlight GENESIS's strengths in managing distributed communication between agents while relying on an autopilot system to simplify the aircraft's flight control.

**Detailed Use Case Description**
1.  **Scenario Description:**
    -   The ATC agent acts as the command authority, issuing navigation and clearance instructions to the aircraft agent.
    -   The aircraft agent interprets, acknowledges, and executes commands using a predefined autopilot system.
    -   Real-time monitoring and logging capabilities ensure visibility into system performance and communication integrity.
2.  **Core Components:**
    -   **ATC Agent:**
        -   Issues commands such as takeoff clearance, heading adjustments, altitude changes, and speed controls.
        -   Monitors the aircraft's state and provides real-time feedback or updates to instructions.
    -   **Aircraft Agent:**
        -   Executes received commands via an integrated autopilot system.
        -   Periodically reports its state (e.g., heading, altitude, speed) to the ATC agent.
    -   **GENESIS Framework:**
        -   Acts as the intermediary for message exchange, ensuring reliable and secure communication.
        -   Manages agent registration, command delivery, and logging for after-action review.

**Functional Requirements**
1.  **Command and Response Handling:**
    -   The ATC agent must issue commands in real-time, including:
        -   Takeoff clearance (e.g., "Cleared for takeoff, runway 31").
        -   Heading changes (e.g., "Turn left heading 270").
        -   Altitude adjustments (e.g., "Climb to 12,000 feet").
    -   The aircraft agent must:
        -   Acknowledge receipt of commands (e.g., "Roger, climbing to 12,000 feet").
        -   Execute commands using the autopilot system.
        -   Periodically report its state to the ATC agent.
2.  **Real-Time Monitoring and State Synchronization:**
    -   The GENESIS framework must ensure that:
        -   State updates (e.g., current heading, altitude) from the aircraft are relayed to the ATC agent without delay.
        -   Commands issued by the ATC agent are delivered and acknowledged promptly.
3.  **Logging and Traceability:**
    -   GENESIS must log all interactions between agents, including:
        -   Commands issued and acknowledgments received.
        -   State updates from the aircraft.
        -   Any errors or missed communications.
4.  **Resilience and Error Handling:**
    -   The system must handle communication interruptions gracefully:
        -   Retry undelivered commands.
        -   Log communication errors for debugging.
        -   Ensure that agents can reconnect and resume operations seamlessly after a disruption.
5.  **Scalability for Future Use Cases:**
    -   The framework must support the addition of multiple agents (e.g., additional aircraft or ATC towers) in future iterations without significant changes to the architecture.

**Expected Outcomes**
1.  **Demonstrated Agent Communication:**
    -   Showcase seamless communication between the ATC and aircraft agents, including real-time command issuance, acknowledgment, and execution.
2.  **Validated Distributed Framework:**
    -   Highlight GENESIS's ability to manage distributed agent interactions, including dynamic registration, message routing, and state synchronization.
3.  **Operational Insights:**
    -   Generate comprehensive logs and visualizations of agent interactions, providing valuable data for performance evaluation and debugging.
4.  **Stakeholder Value:**
    -   Deliver a tangible demonstration of GENESIS's potential for real-world applications in aviation and defense.
5.  **Foundation for Future Scenarios:**
    -   Establish a robust framework that can be extended to include more complex scenarios, such as multi-agent collaboration or UAV swarm operations.

**Use Case Workflow**
1.  **Initialization:**
    -   Launch GENESIS to register and initialize the ATC and aircraft agents.
    -   Connect the autopilot system to the aircraft agent.
2.  **Scenario Execution:**
    -   *Step 1:* ATC agent clears the aircraft for takeoff.
        -   Command: "Cleared for takeoff, runway 31."
        -   Aircraft agent acknowledges and begins takeoff.
    -   *Step 2:* ATC agent issues navigation commands.
        -   Example: "Turn left heading 270, climb to 12,000 feet."
        -   Aircraft agent adjusts its autopilot and reports its state: "Current heading 270, altitude 8,000 feet."
    -   *Step 3:* ATC agent monitors compliance and issues further instructions as needed.
3.  **Monitoring and Logging:**
    -   Use GENESIS to visualize aircraft state and log all interactions for post-scenario review.
4.  **Agent Substitution:**
    -   Demonstrate the ability to change agents from human to artificial.
5.  **Simulation End:**
    -   ATC agent issues a termination command (e.g., "End simulation").
    -   GENESIS archives session logs for analysis.

**Conclusion**
The detailed definition of the ATC and Aircraft Interaction Simulation sets a clear foundation for implementation. This use case will demonstrate GENESIS's capabilities in distributed agent communication while providing operational insights for future development. Task 2.4 will decompose this use case into functional components to guide the development and integration of the simulation.

#### Task 2.4: Decompose the System into Functional Components to Guide Development and Integration

**Overview**
To implement the ATC and Aircraft Interaction Simulation effectively, the system must be broken down into modular functional components. This decomposition ensures clarity in design, streamlined development, and ease of integration within the GENESIS framework. Each component will fulfill a specific role, and together they will deliver the simulation's full functionality.

**Functional Component Decomposition**
1.  **GENESIS Framework Core**
    -   *Responsibilities:*
        -   Manage the communication backbone between agents.
        -   Handle agent registration, message passing, and error recovery.
        -   Provide logging, monitoring, and replay capabilities.
    -   *Key Subsystems:*
        -   **Service Registry:** Tracks active agents, their roles, and capabilities (e.g., ATC tower, aircraft).
        -   **Classifier/Functions:** Classifies request to determine if additional services are needed to complete the request
        -   **Logging and Replay System:** Captures all interactions for debugging and after-action reviews.
2.  **ATC Agent**
    -   *Responsibilities:*
        -   Issue commands to the aircraft agent (e.g., takeoff clearance, heading adjustments, altitude changes).
        -   Monitor aircraft state and provide real-time feedback.
        -   Validate command acknowledgments and compliance.
    -   *Key Features:*
        -   **Command Generation Module:** Generates commands in response to the aircraft's state and scenario requirements.
        -   **State Monitoring Module:** Continuously tracks aircraft state updates via GENESIS.
        -   **Error Detection:** Identifies and logs communication or compliance errors.
3.  **Aircraft Agent**
    -   *Responsibilities:*
        -   Receive, acknowledge, and execute commands issued by the ATC agent.
        -   Report current state (e.g., heading, altitude, speed) back to the ATC agent.
        -   Integrate with the autopilot system for executing commands via agent connections and classifier identified function calls.
    -   *Key Features:*
        -   **Command Interpreter:** Parses and validates incoming commands.
        -   **State Reporting System:** Sends periodic updates to the ATC agent.
        -   **Autopilot Interface:** Translates commands into inputs for the autopilot system.
4.  **Autopilot System Integration**
    -   *Responsibilities:*
        -   Control the aircraft's behavior based on commands received from the aircraft agent.
        -   Maintain internal state (e.g., heading, altitude, speed) and update the aircraft agent.
    -   *Key Features:*
        -   **Execution Module:** Adjusts flight parameters in response to ATC commands.
        -   **Feedback Loop:** Reports execution success and current state back to the aircraft agent.
5.  **Monitoring and Visualization Tools**
    -   *Responsibilities:*
        -   Provide real-time visualization of agent states and interactions.
        -   Display the aircraft's position, heading, altitude, and speed in a user-friendly interface.
    -   *Key Features:*
        -   **Dashboard:** Displays a map overlay (e.g., Google Maps or a 3D simulation tool) for real-time visualization.
        -   **Interaction Timeline:** Logs and visualizes all agent commands, acknowledgments, and state updates.
6.  **Resilience and Error Handling**
    -   *Responsibilities:*
        -   Ensure system continuity during communication interruptions or agent failures.
        -   Provide mechanisms for agent reconnection and state recovery.
    -   *Key Features:*
        -   **Error Detection and Recovery:** Automatically retries failed messages and logs errors for review.
        -   **Agent Failover System:** Substitutes failed agents (e.g., swapping human ATC control with an AI agent).
7.  **Logging and Analytics System**
    -   *Responsibilities:*
        -   Capture all system interactions for debugging, evaluation, and stakeholder reviews.
    -   *Key Features:*
        -   **Interaction Logs:** Record commands, acknowledgments, state updates, and errors.
        -   **Data Export:** Enable export of logs for external analysis or reporting.
        -   **Replay System:** Reconstruct simulations for after-action reviews.

**Integration Points**
-   **DDS Communication Backbone:**
    -   All agents and subsystems communicate via the Connext Databus, leveraging DDS for real-time, low-latency message passing.
-   **Autopilot System Interface:**
    -   Integration with the existing autopilot system ensures commands translate directly into flight behaviors.
-   **Visualization Tools:**
    -   Connect the GENESIS framework to visualization platforms (e.g., Unity, Unreal Engine, or Google Maps) for real-time feedback.
-   **Agent Substitution:**
    -   Implement a flexible architecture allowing dynamic substitution of agents (e.g., replacing a human ATC agent with an AI agent).

**Development Workflow**
1.  **Core Framework Development:**
    -   Implement the GENESIS framework's service registry, classifier/function calling, and logging subsystems.
    -   Validate communication reliability and state synchronization.
2.  **Agent Development:**
    -   Develop the ATC and aircraft agents with modular components for command handling, state reporting, and error detection.
3.  **Autopilot Integration:**
    -   Establish interfaces for sending commands to and receiving state updates from the autopilot system.
4.  **Visualization and Monitoring:**
    -   Create a dashboard for real-time monitoring and implement visualization tools to display agent states and interactions.
5.  **Resilience and Testing:**
    -   Test the system under various failure conditions (e.g., dropped messages, agent failures) and refine error-handling mechanisms.

**Conclusion**
By decomposing the ATC and Aircraft Interaction Simulation into these functional components, development can proceed in a structured and modular manner. Each component addresses a specific aspect of the simulation, ensuring scalability, maintainability, and seamless integration. This approach provides a clear roadmap for building a robust and extensible system that meets the project's objectives.

---

_Figure 3: Current I/ITSEC Demo. GENESIS and Simulink will be integrated with this existing demo._

_Figure 4: SimBlocks.io OneWorld view for the current demo._

---

**TPOC AIs**
-   We are anticipating working with others and further refining GENESIS based on the TPOC's other engagements. We await introductions.

**Non-Development Updates –**
No new updates.

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

**Plans in the next 2-month period:**
-   Task 3.1: Complete the evaluation of the early approach based on engagements to date.
-   Task 3.2: Finalize the data modeling analysis for basic messaging structures and methods.
-   Task 3.3: Refine the early prototype architecture to establish a base line internal core framework.
-   Task 3.4: Implement the internal framework.

### 4.5 Task 4: Inter-agent Library Design & Implementation, Demonstration

**Plans in the next 2-month period:**
-   Task 4.1: Down select the initial target library environment.
-   Task 4.2: Implement the initial library based on the target architecture.

### 4.6 Task 5: Simulink/MATLAB Use Case Integration

**Plans in the next 2-month period:**
-   Task 5.1: Work with stakeholders to ensure that targeted use cases are still highly relevant.
-   Task 5.2: Refine the architecture based on feedback from demonstrations to stakeholders.
-   Task 5.3: Architect the use case with the refined distributed AI agent architecture.
-   Task 5.4: Design and implement any needed agents for the targeted use cases within the Simulink/MATLAB environment.

### 4.7 Task 6: Architecture Refinement, Security Access and Dataflow

**Task Not Started.**

**Plans in the next 2-month period:**
-   N/A

### 4.8 Task 7: Agent Service Registry Design, Implementation, and Demonstration

A skeleton service registry exists but much refinement and feature work must be done.

**Plans in the next 2-month period:**
-   N/A

### 4.9 Task 8: Semantic Security Service Layer, Design, & Implementation

**Task Not Started.**

**Plans in the next 2-month period:**
-   N/A

### 4.10 Task 9: Multi-Agent Framework Library Development & Demonstration

**Task Not Started.**

**Plans in the next 2-month period:**
-   N/A

### 4.11 Task 10: Documentation

**Task Not Started.**

**Plans in the next 2-month period:**
-   N/A

---

## 5 Appendices (Task Detailed Updates)

### Development

We met internally in early August to sync AI work within RTI. The goal of the meeting was to unify approaches and share knowledge within RTI for various AI agent efforts. Following this meeting we began an architecture review from previous GENESIS work and implementations. We evaluated and refined the service registry and initial agent reference implementation, an initial interface reference implementation, and began early classifier and function work. The initial architecture depends upon a service registry coordinating agents, interfaces, and functions through the use of a classifier. This very early framework is not persistent and cannot recover from unanticipated interruptions.

On August 16th, 2024, we had a meeting with Mathworks for the target demo period here is the summary of that meeting:

1.  RTI is developing a project called GENESIS, which is a distributed multi-agent framework for generative and reinforcement learning, using DDS for communication and discovery.
2.  The project involves two phases:
    -   Phase 1: Awarded to RTI and three other companies, focusing on rapid integration tools.
    -   Phase 2: Already awarded to RTI, focusing on core GENESIS development and Simulink integration.
3.  The primary government contact is Kevin Kelly from PEO Digit (Air Force), who wants a demonstration involving a simulated surveillance plane scenario.
4.  RTI's role includes:
    -   Developing the communication framework (GENESIS)
    -   Creating tools for rapid integration and deployment
    -   Potentially coordinating between different performers
5.  Simulink is the target environment for simulations, though the exact implementation details are still uncertain.
6.  RTI is currently working on a demo using a UAV model in Simulink but is facing some compilation and licensing issues.
7.  MathWorks offered support in resolving immediate technical issues and discussed potential future collaboration if the project proves valuable to their commercial customers.
8.  The project aims to create a modular, secure environment for distributed AI agents, particularly focused on defense applications.
9.  Next steps include:
    -   Resolving licensing issues with MathWorks
    -   Scheduling a technical session to address current blocking issues
    -   Waiting for more information on what the other Phase 1 awardees will contribute
10. There's potential for further collaboration between RTI and MathWorks, depending on how the project develops and its potential commercial applications.

In late August into September, we began investigating Simulink integration. We investigated how to do user interfaces within Simulink. The Simulink interface for MATLAB has both an external and internal mode. The external mode uses MATLAB as a compiler to compile external code. The initial tests were to capture DDS data within Simulink and generate DDS data from within Simulink. These initial tests had mixed results, and we scheduled meetings with MATLAB.

To continue on our Simulink work we completed an initial demo that used DDS data to map an aircraft over Google Maps. While not integrated into GENESIS yet we demonstrated an ability for a prompt to be used to send agent data to and from a user interface that included the map overlay. The target was to create a converter from semantic messages to a lat/long that would position a drone centered in Washington DC. This demonstration was successful. This demonstration can be used to show a simplified demo and the takeaways from this demonstration can be used for more elaborate demonstration.

During this period, we also located an internal demonstration that was presented at I/ITSEC in 2022 and 2023. It represents a mature demo that leverages DDS to simplify complexity across multiple flight simulations and data providers. This demo is now targeted for the GENESIS demo for this project. We will integrate both GENESIS and Simulink into this demo and provide that demo to awardees that wish to participate for the AFWERX phase one managed by the TPOC.

### Project Management / Stakeholder Development

During this reporting period we met with the TPOC twice. We have refined the target prototype consisting of a simulation that includes an airplane with a pilot and a tower communicating via text and/or voice to coordinate aircraft control. The point of the demo is not to fly the aircraft but use semantic communications to demonstrate that a coordination between an AI tower and AI pilot can be substituted at will for a human agent. This demo represents a path forward for a much more complex demonstration with multiple agents, multiple humans, and multiple endpoints that include towers aircraft and possibly ground vehicles.

Also, during this period. We met with Air Force CyberWorx, which is local to the Colorado Springs area. The purpose of this meeting was to identify target environments and stakeholders to assist PEO Digital in promoting GENESIS to the broader Air Force. We will continue to monitor this engagement and follow up as necessary.

---

**END OF REPORT**

