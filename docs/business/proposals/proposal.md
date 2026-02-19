A Data-Centric Distributed Agentic Framework for DAF Simulation

Table of Contents

TABLE OF CONTENTS	I
1	TECHNICAL SUMMARY	1
1.1	IDENTIFICATION AND SIGNIFICANCE OF THE PROBLEM OR OPPORTUNITY	1
1.1.1	GENESIS PROJECT OVERVIEW	2
1.2	DEPARTMENT OF THE AIR FORCE OPERATIONAL IMPERATIVES	3
1.3	NON-DEFENSE COMMERCIAL SOLUTION	3
1.4	PROPOSED ADAPTATION OF NON-DEFENSE COMMERCIAL SOLUTION	5
1.4.1	SOLUTION SET TO IDENTIFIED REQUIREMENTS	5
1.4.2	ARCHITECTURE	6
1.5	PHASE I ‘FEASIBILITY STUDY’ RESULTS	7
1.6	COMPLIANCE AND REGULATORY ACTIVITIES	8
1.7	PHASE II TECHNICAL OBJECTIVES AND KEY RESULTS 	8
2	PHASE II WORK PLAN (NON-PROPRIETARY)	9
2.1	SCOPE	9
2.2	TASK OUTLINE	9
2.3	MILESTONE SCHEDULE (NON-PROPRIETARY)	11
2.4	DELIVERABLES	12
3	COMMERCIALIZATION STRATEGY	12
4	MILITARY APPLICATIONS/DOD CUSTOMERS	14
5	FOREIGN PERSONS	14
6	KEY PERSONNEL	14
7	NON-DEFENSE COMMERCIAL CUSTOMERS	15
8	INVESTORS AND PARTNER	15
9	RELATED WORK	15
10	REFERENCES	15

 
GLOSSARY

A&D - Aerospace and Defense (Market Segments)
ABMS - Advanced Battle Management System
AFLCMC - Air Force Life Cycle Management Center
AFRL - Air Force Research Laboratory
AFSIM - Air Force Synthetic Environment for Scenario Simulations
AWS - Amazon Web Services
CAI - Commercialization Achievement Index
CMSO - Chief Modeling and Simulation Office
COTS - Commercial-Off-the-Shelf
DAF - Department of the Air Force
DDS - Data Distribution Service
DoD - Department of Defense
DO-178C - Software Considerations in Airborne Systems and Equipment Certification
HWIL - Hardware-In-The-Loop
IRAD - Internal Research and Development
ISO26262 - International Standard for Functional Safety of Electrical/Electronic/Programmable Electronic Systems
ITAR - International Traffic in Arms Regulations
LLM - Large Language Model
M&S - Modeling and Simulation
MOSA - Modular Open Systems Approach
OMG - Object Management Group
PEO - Program Executive Office
QOS - Quality of Service
RTI - Real-Time Innovations Inc.
RTOS - Real-Time Operating System
SBIR - Small Business Innovation Research
SBC - Small Business Concern
SBIR - Small Business Innovation Research
Simulink - MATLAB-based graphical programming environment for modeling, simulating, and analyzing multidomain dynamical systems
STRATFI - Supplemental Funding Pilot Program Strategic Funding Increase
STRIDE – A security model for identifying computer security threats (Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevations of privilege
TRL - Technology Readiness Level
STRATFI - Supplemental Funding Pilot Program Strategic Funding Increase 

RTI’s PROPOSAL CRITERIA SNAPSHOT
CRITERIA A – Commercialization Potential
•	RTI’s Commercialization Record: We are rated in the top 1% of all SBIR-funded companies to commercialize SBIR results with more than 50 SBIR awards (our commercialization achievement index is 100). We leverage SBIR funding to commercialize defense-related capabilities.
•	Market size: include both RTI’s defense and markets already pursuing generative AI, we estimate $10M/yr once matured, with an annual growth of over 20%-30% after that.
•	Follow-on defense and commercial commitments:
o	While PEO Digital and AFRL have no funding to contribute in 2024, because it is critically important to them, we will work with them on an accelerated plan to transition GENESIS to USAF AFSIM.
•	Transition Plan: Per directions, our transition strategy is detailed in Section 9 of the Customer Memorandum
CRITERIA B – Defense Need
•	DAF is heavily funding numerous efforts to evaluate and integrate generative AI (via agents) into numerous systems.  Our DAF End Customer/User have stated that AI efforts are hindered by integration hurdles into simulation and training tools like AFSIM. Our proposal seeks to commercialize a full stack open-standards solution with AFSIM as PEO Digital’s integration target in order to accelerate warfighter training; with RTI’s foundational technology running in over the 1,400 DoD applications, many opportunities exist.
•	Adequacy of the Proposed Effort: PEO Digital, AFRL CMSO, and RTI designed and scoped this solution through collaborative effort.
•	Mission Impact and Urgency: The exponential performance curve of general and specialized generative AI is severely outpacing integration into real systems. It is expected that generative AI combined with simulation will far exceed human performance in a wide range of tasks prior to 2030!  This effort DIRECTLY addresses integration of collaborative AI and simulation.  This effort is critical to help the US outpace threats.
CRITERIA C– Technical Approach
•	Technical Merit/Approach: We designed this approach with PEO Digital and AFRL CMSO. Our solution’s communication backbone, the OMG DDS communications standard, was chosen by PEO Digital (independent of RTI) because of its battle-tested features related to simulation support, modularity, scalability, security, & resilience.
•	This effort focuses on a design and integration for AI specific services and frameworks into a cohesive simulation environment.  We are taking a TRL-9 communication product with $100M in design and optimizations and augmenting it with specific solutions to serve a targeted purpose.
•	Staffing includes Ph.D. and M.S. engineers and researchers with expertise in distributed communications and AI in cooperation with MathWorks, the owner of Simulink, the target environment specified by DAF.
1	Technical Summary
1.1	Identification and Significance of the Problem or Opportunity 
The promise of generative AI and generative agents is very likely world changing and nowhere will this be seen more acutely than on the battlefield.  AI agent augmentation in weapons platforms, training, information management, target recognition, intelligence analysis, and the myriads of other applications will be a necessary discriminator for the warfighter. Due to generative AI agent potential, PEO Digital and AFRL USAF CMSO are investing heavily in generative AI agents to interact with simulation systems.  This ongoing work shows increasing promise due to the exponential performance gains in general LLMs and agent frameworks; however, they have identified several technology gaps to their goal of a “safe, secure, reliable” integration of generative AI agents into simulation environments. Beyond implementation specifics, DAF suffers the same integration hurdles that the larger commercial tech industry suffers from, which is integration of these independent generative agents into a cohesive framework integrated with a meaningful system, commonly called “completing the stack”.  In short, DAF has promising AI technologies that will be a force multiplier for the warfighter and a robust simulation environment; however, DAF lacks a “safe, secure, reliable” bridging stack to make it all work together.  They require a standardized, stable, robust framework for AI agent interaction between agents, humans, and the target environment that allows for rapid deployment and integration of cutting-edge AI technologies.  
Over the course of months of discussions with PEO Digital and USAF CMSO on this topic, we have identified the three challenges below and we frame them in PEO Digital’s “safe, secure, and reliable” theme:
C1.	Safe: Safety within a multi-agent framework is all about dealing with complexity.  AI models and agents are largely non-deterministic and heavily rely on correct prompting to achieve desirable results. Generative AI prompting has become its own field to guide generative AI down the correct paths to success. Managing prompts (system and user), context, and the correct and limited delivery of this information will be a primary challenge in this project. Agent performance is a unique challenge to the generative AI problem set that seeks to achieve agent decision reliability through prompts, in-context learning, training, and machine learning. In a multi-agent environment, this contextual data must be made available synchronously for machine and in context learning, and asynchronously for model training.
C2.	Secure: All current AI agent frameworks rely on basic security measures like wire encryption (if at all), which is insufficient for comprehensive security.  Implementing advanced security capabilities, include authentication, encryptions, and access control is crucial, yet challenging due to the interconnected nature of distributed AI agents. To make matters more complex, AI models (and consequently their agents) can be socially engineered by manipulating prompts, system prompts, and any other in context messaging
C3.	Reliable: Reliability challenges can be separated into three categories.  Reliability in agent integration; reliability in messaging; and reliability system integration.  The primary challenge in multi-agent interaction and integration lie in the fact there is no standard communication layer that exists between agent frameworks (and in some instances, within agent frameworks).  These communication connections must currently be home grown and while narrow scope interactions between two agents is trivial, a fully distributed agentic framework is complex in the extreme. In the same light, messaging reliability in the simple context is trivial but becomes quit complex in a distributed system with multicast messages. Further, none of the challenges in system integration are likely to be trivial and are currently the significant hurdle for even “one-off” agents to become useful.  
1.1.1	GENESIS Project Overview
In response to the challenges encountered by PEO Digital and AFRL USAF CMSO in their effort to bring generative AI to warfighter training & operational use, we propose to build a Data-Centric Distributed Agentic Framework called GENESIS: Gen-AI Network for Enhanced Simulation Integration and Security: (Figure 1)
 
Figure 1: GENESIS will help unleash the power of generative AI for warfighter training and operational use cases.
We identified the following set of high-level requirements that, if addressed, will enable the design and development of a safe, secure, reliable, and interoperable AI agent framework. They form the basis of our proposal to design and develop the GENESIS framework.
R1.	Safe: GENESIS will require semantic level monitoring sufficient to use data for future training and/or in-context learning for system repeatability, correction, and safety.  This data must be available for access both synchronously and asynchronously. 
R2.	Secure: GENESIS will require agent and interface level access control.  This access control must be authenticated with industry standard security mechanisms and used to maintain secure during message transit.  Further, GENESIS must also employ semantic security to prevent unintentional or malicious misbehaviors unique to generative AI agents.
R3.	Reliable: GENESIS will require a standardized, open communication layer for agent-to-agent and agent-to-human communication with supporting integrations into common agent frameworks (Semantic Kernel, LangChain), AI programming languages (Python, C#, Javascript), and model inference endpoints (HTTPS). This communication layer must be robust, scale, and preferably tested in relevant environments.  Finally, GENESIS must integrate with Simulink during the Phase II with a target integration with AFSIM in post Phase II follow on efforts. Within the timeframe and funding of the Phase II effort, our objective is to address each of these requirements though the design and implementation of a generative, multi-agent communication framework that is safe, secure, and reliable by using an industry leading, robust communication framework that is battletested in more than 1,400 DoD applications.
1.2	Department of the Air Force Operational Imperatives 
The proposed GENESIS framework addresses several key USAF operational imperatives.  Specifically, it supports Operational Imperative 2: Advanced Battle Management System (ABMS) by providing a secure, distributed communication framework that enhances situational awareness and decision-making capabilities with a focus of moving Generative AI agents beyond conceptual demonstrations and experiments. GENESIS's ability to integrate AI agents with existing simulation environments like MATLAB/Simulink and AFSIM aligns with Operational Imperative 4: Connected Joint Force, enabling seamless data sharing and interoperability across different systems and domains. Additionally, the framework's focus on robust security and scalability supports Operational Imperative 5: Agile Combat Employment, ensuring resilient and adaptive AI-driven operations. By enhancing multi-domain command and control capabilities, GENESIS directly contributes to the strategic objectives of the USAF, fostering a more connected, secure, and efficient operational environment. Finally, the ability of the framework to accept new/updated agents for collaboration in a plug-and-fight fashion supports Operational Imperative 7: Readiness to Deploy and Fight.
1.3	Non-Defense Commercial Solution
Real-Time Innovations, Inc. (RTI) is a commercial software vendor.  We develop a secure, real-time communications high assurance framework for both industrial and defense systems.  RTI Connext DDS is a set of developer tools, a software library that is compiled into an application, and additional runtime services that enhance its use; it provides all of the distributed communications services needed within any system.  RTI Connext DDS developer licenses, support, and services accounts for most of RTI's revenue – approximately $50M in 2023.  Our customers buy RTI Connext DDS because it provides all of the distributed communications needs for their small to extremely large critical distributed systems. It is scalable, secure, robust, proven, and promotes MOSA.  It enables them to build their systems using less code and more modularity, substantially reducing the cost of their systems[3].
Connext DDS implements the OMG DDS standard[1][2].  The standard ensures that all compliant products are interoperable at both the wire level and API level.  This means that applications built by different teams using various competing vendor products will all interoperate with very little effort.  RTI Connext DDS is in over 1,700 commercial applications and 600 research programs, including: NASA's KSC launch system, simulators, autonomous/electric commercial vehicles, ground stations, aircraft, ships, satellites, medical devices, power utilities, and many other mission-critical systems. It has also been used as the foundation for HWIL simulation and testing for both ground and airborne vehicles (e.g, Volkswagen, Passaro/Airbus).  Key to this proposal, DDS provides access control/security, self-discovery, years of operational deployment in critical systems, scales to incredibly large environments, and is an open standard with both open source and many commercial implementations.
Specialized versions include RTI Connext DDS Micro, the world’s first DO-178C Level A certified middleware that implements a flight safety certifiable subset of the DDS specification. This TRL-9 product is being used by military and commercial customers in many industries. 
In the following discussion, we describe the DDS standard in general, and not just our commercial product, which is fully DDS compliant.  This also applies to other commercial implementations of DDS.
DDS is data centric – it treats data as a first-class citizen.  Most other communications solutions are message centric and send their data over the network as opaque payloads that the network cannot understand. Only the applications themselves do because all of the knowledge about encoding and decoding the data rests with them. This forces every application to reinvent features for reliability, security, fault tolerance, scalability, and end to end interoperability.  
In contrast, data centric means that developers naturally define open data models that describe the structure of the data that will move between applications.  This allows DDS to automatically handle encoding, security, optimized/reliable delivery, and more.  It also means that the government can own the interfaces, while the prime owns the implementation. DDS offers the government a real path to modular open system architectures (MOSA).
RTI Connext DDS is a loosely-coupled, and fully decentralized communications framework.  This makes it possible to scale systems quickly, without recompiling or shutting the systems down.  Instead of creating brittle, point-to-point network dependencies, DDS communicates over the concept of topics.  Applications simply declare what kind of data (topics) they are interested in and DDS delivers it.  This eliminates the brittleness of requiring endpoints to identify their communications peers – DDS handles all of this via a dynamic discovery handshake process, so developers can focus on application code rather than reinventing how to send data over the network.  
DDS provides fine-grained read/write access control to the data.  While encrypting all communications is generally useful, when a system only wants to restrict subsets of the data this approach will not work.  Using DDS fine-grained access control guarantees that only authorized applications receive this data – enabling highly customizable multi-level secure communications.  This is software-defined security [2].   
Finally, the loosely coupled nature of DDS and its use of topics to communicate both support location-independent processing.  This promotes system modularity and resilience, a key benefit of MOSA system design.
1.3.1	Answers to Questions In The Instructions:
Does the proposed solution represent an entirely novel standalone solution or does it modify/build upon an existing product or service? Our distributed agentic framework builds upon the RTI Connext DDS product suite, which is currently sold to both commercial and defense companies.  RTI’s sales of Connext DDS exceeds $50M/year.
Has the proposed solution been (i) sold, leased, or licensed to the public; OR (ii) offered for sale, lease, or license to the public? Provide quantifiable data evidencing this sale, lease, or licensing. The enhancements to RTI Connext DDS are new and therefore have never been sold. 
What is the non-defense market opportunity of your proposed solution? We believe that more than 75% of our industrial customers will be very interested in GENESIS, and therefore estimate a non-defense commercial market opportunity of > $10M/year for these new features, once it is commercialized. 
Is the proposed item “of a type”, i.e., similar to a commercial item.  Not today.  While agent frameworks abound, our focus on creating a fully distributed multi-agent framework is completely novel.  OMG DDS is an ideal and revolutionary solution to enable modular, scalable, and secure distributed agent capabilities.  We are bringing a battle-proven, operationally high-performance technology to bear to help drive the rapid advancements in AI for the DAF.
What are the end-user use cases for the proposed solution and how does the proposed solution fulfill these use cases? The latest generative AI research has demonstrated amazing abilities when combining multiple agents.  For our identified end users, they want GENESIS to substantially improve warfighter training and their operational performance by leveraging the rapid advances that generative AI has already demonstrated. Our framework will help to accelerate the development, deployment, and integration of modular, open, secure and resilient training solutions for our warfighters.
How is the proposed solution different from similar competitor solutions?  Existing solutions are focused on developing single agent applications.  They are not modular – meaning that one cannot easily/quickly integrate agents from other contractors/companies/frameworks; they are not secure – meaning that the data communications is not protected, and they don’t have security to prevent data leakage; they cannot easily scale to hundreds or thousands of agents; they do not support an ability to discover new agents to interact with.  We are focusing on these profoundly enabling capabilities.
What are the proposed solution’s technical risks and how are they mitigated?  As global leading experts in distributed systems, we bring the breadth and depth required – along with a proven foundation of technology (OMG DDS)– that will be required.  The primary technical risks will be related to the Phase II integration with Mathworks Simulink (per our customer’s request), and addressing limitations to their interfaces, if any.  However, we have an excellent relationship with Mathworks [6], Simulink already supports Connext DDS [5], and they are very supportive of our proposal (see their letter of support).
What is the proposed solution’s technical readiness level, and have any previous results shown the technology’s viability? Include, where applicable pre-sales, pilots, sales, revenue, active users, subscriptions, downloads, and/or other forms of traction/adoption for the proposed solution.  GENESIS itself is at TRL-2 based on related work done under an existing USAF SBIR Phase II effort and IRAD funding – detailed below in Section 1.5 (Phase I ‘Feasibility Study’ Results).
1.4	Proposed Adaptation of Non-Defense Commercial Solution 
RTI brings two major non-defense commercial solutions to this proposal.  First is our TRL-9 Connext product, which is an interoperable implementation of the OMG DDS standard in use in 1,440 DoD applications as well as supported by Simulink/MATLAB, the target environment identified by PEO Digital.  Second is our TRL-2 distributed generative AI framework, based on the DDS standard, which was used as a feasibility study to derisk the use of DDS as a communication framework for inter-agent communication. We currently do not have competition – our solution is a unified framework that will facilitate the integration of, and interaction between, existing agent frameworks.
 
Figure 2: GENESIS will provide Full Stack Multi-Agent Simulation Integration – it will enable DAF systems to rapidly reap the potential from dynamically interacting AI agents. GENESIS is an open-standards, modular, secure, and reliable framework that will make it possible to quickly integrate AI agents from many contractors and other sources.
1.4.1	Solution Set to Identified Requirements
The details of the solution set encompassed by GENESIS are described by S1-S3 below. 
S1. Safe: GENESIS will ensure the safe operation of AI agents within the framework through comprehensive state monitoring and interaction. GENESIS will leverage the capabilities of the Object Management Group Data Distribution Service for Real-Time Systems (OMG DDS). DDS provides a robust framework for real-time data exchange, already used in thousands of critical real-time systems across various industries.  RTI Connext DDS, our flagship product, serves as the software connectivity foundation for numerous cross-industry open standards. This commercial communication framework provides scalable, real-time data exchange, an extensive quality of service (QOS) capability [4], and logging.  We intend to extend the services for GENESIS to provide semantic level monitoring and reviewable interactions that will allow for more nuanced oversight, going beyond simple data monitoring to understand the intent and content of communications. By integrating these features, GENESIS will ensure that the operation of AI agents is safe, transparent, and accountable. The comprehensive monitoring capabilities will not only enhance operational safety but also facilitate continuous improvement through detailed analysis and feedback
S2: Secure: GENESIS will leverage the existing security mechanisms within RTI Connext DDS, which include DoD-approved encryption methods and authentication protocols. These features include certificate-based authentication, encryption, and access control already in use with DoD. The framework will be enhanced with additional semantic controls to further secure agent interactions.  By combining these robust security measures, GENESIS will provide a secure environment for AI agents to interact and collaborate, ensuring the integrity and confidentiality of the system.
S3: Reliable: GENESIS will provide an open, standardized communication layer using the OMG DDS standard for agent-to-agent/human/interface/data/service communications. RTI’s Connext DDS provides, proven, extreme message reliability out of the box for this project. GENESIS will ease integration of agents by providing communication libraries for widely used agent frameworks such as Semantic Kernal and LangChain in their supported languages (Python, C#, and JavaScript).  Lastly, GENESIS will used the current DDS-Simulink integration to overcome the system integration requirement.
1.4.2	Architecture
As rendered in Figure 2, the core communication framework for GENESIS will be RTI Connext DDS, though other implementations of DDS could be substituted with little effort. DDS provides a several key solutions out of the box to include:
•	Discovery: Endpoints can join the network and discover other endpoints without any network configuration.
•	Security: Access control, authentication, and encryption are handled by DDS out of the box
•	Data delivery: Data is presented to endpoints as known structures; no data serialization is handled by the endpoints.
•	Content Filtering and Keying: Endpoints only send data if it is desired by other endpoints.
•	Multicasting: Endpoints can send data to multiple endpoints with sublinear network resource usage.
Using DDS as the backbone achieves many of the key solution points within the safe, secure, reliable framework.  What remains focuses on AI agent specific requirements as well as the full stack integration with Simulink. These extensions consist of creating AI agent specific services, abstracting these services from the end user, and integrating with Simulink.  
Services include a logging and query service that will allow for agents, other services, and/or analysts to monitor system state prior/post agent output.  This is a key component to the “Safe” requirement and will allow for optimization, model training, and auditing of the system for continuous improvement. RTI already has technologies for this type of logging and they will be modified for this specific use. The “Secure” requirement also requires a service for semantic security monitoring and decision. As this is a semantic service, it’s implementation will be a system level agent.  Another service that is required is a service registry. This could be built as an application or incorporated into endpoint libraries for the discovery of services and other agents in the system. This registry is a key addition to the “Reliable” requirement as it allows for agents to be “pluggable” into the framework, discover, and communicate with other agents, services, and data.  Finally, a security infrastructure will be needed to enforce access control.  We will use a COTS service for this.
For services to be utilized seamlessly, endpoints must contain code for these services and many of them should be abstracted from the agent.  To accomplish this, we will incorporate the service calls into the agent libraries.  Three of these libraries will be built, one each in Python, C#, and JavaScript to cover the most used languages for agent frameworks (LangChain and Semantic Kernel).  These libraries will transparently handle service calls in most cases but make available specific service calls for agents intended to access services directly (e.g. a ML agent optimizing prompting from logged data).
Finally, full stack integration with Simulink will be accomplished early in the project to avoid pitfalls later in the project.  Simulink already supports DDS; however, this early incorporation will identify any issues that may arise to ensure the overall project goal of a safe, secure, reliable, multi-agent framework integration with a simulation environment to support DAF identified requirements.
Our objective for GENESIS is to build upon RTI's commercially mature and proven MOSA software communications framework and extensive past / ongoing R&D efforts to:
Explore, develop, and deliver a Safe, Secure, Reliable Generative-AI integration framework for Air Force Simulation & Training Systems, and beyond.

1.4.3	Answers to Questions In The Instructions:
How similar is the modified item to others sold in the commercial marketplace to non-US Government customers?  Related, however existing solutions are focused on developing single agent applications, in a single framework, in a single language.  They are not modular – meaning that one cannot easily/quickly integrate agents from other contractors/companies; they are not secure – meaning that the data communications is not protected, and they don’t have security to prevent data leakage; they cannot easily scale to hundreds or thousands of agents; they do not support an ability to discover new agents to interact with.  We are focusing on these profoundly enabling capabilities.
Does the supplier perform similar modifications for non-US Government customers?  Yes – RTI provides feature enhancements, custom services, and integration gateways for industrial customers.
Do DAF unique modifications change the product’s essential use and purpose?  No. The proposed enhancements build on top of RTI Connext DDS, adding new market-discriminating features and enhancing the product.  
Are there differences in the production/manufacturing/delivery processes used to perform the modification for the Federal Government versus non-Government customers?  No. 
What are the quantitative benefits expected for identified DAF end-users?  GENESIS is targeting 2x-4x improvements in pilot training, 50-60% reduction in pilot training costs (by eliminating red team pilots), and >40% improvement in operational productivity for our customers’ use cases (AWACS data analyst).
When adapting the commercial solution, what is the intended Commercial-Off-the-Shelf (COTs) modification? This is answered in section 1.4 above.  
If applicable, what Test & Evaluation will be performed on the solution.  We plan to conduct end-to-end testing of GENESIS and its initial integration with Simulink to evaluate its performance, security, usability, and implemented functionality. Our focus is on developing the distributed agentic framework, not on developing the specific training solutions – those will be built on top of GENESIS.
What is the desired outcome of that T&E? The documentation of results that include performance, scalability, security, modularity, and developer ease of use improvements that are needed, and the identification of additional requirements for future versions of GENESIS.

1.5	Phase I ‘Feasibility Study’ Results
Scientific or Technical R/R&D Effort: During early 2023, RTI successfully completed its first distributed agent framework using DDS through IRAD. The framework's capabilities include agent replication and specialization for code generation, targeting the generation of DDS-based code in Python. While the initial framework did not explore security aspects, it effectively demonstrated DDS's capability for inter-agent discovery and validated DDS content filtering as a robust method for directed communication within complex agent frameworks.
DAF End-User and Customer Exploration Methods: The feasibility of adapting this non-Defense commercial solution to DAF needs was explored through direct engagement with DAF stakeholders initiated through an unsolicited contact by Mr. Kelly, PEO Digital, on the topic. Key activities included:
•	We held in-depth interviews with Mr. Kevin Kelly, Tech Director at PEO Digital, and Dr. Jim Gump, Senior Technical Advisor at AFRL. These discussions helped refine the use of DDS as a communication protocol specifically tailored for simulation environments in DAF use cases.
•	Multiple working sessions were held with DAF representatives and RTI's technical team to architect a solution that aligns with the DAF’s vision for Generative AI in simulation.
1.	Empowered and Committed DAF End-Users: Dr. Gump AFRL/CMSO has shown significant interest in the framework's potential to enhance simulation environments. His support extends to further R&D, testing, and evaluation of our Phase II solution, focusing on integrating advanced AI capabilities within DAF’s operational simulations (AFSIM).
2.	Meeting the End-User’s Needs: The proposed architecture represents a joint solution crafted by USAF CMSO, PEO Digital, and RTI based on the feasibility study results, our commercial software product, and, most importantly, direct discussions of DAF challenges with generative AI integration into simulation environments.  It directly addresses the needs for enhanced interoperability and safe, secure, reliable communication within DAF simulations. By leveraging existing commercial DDS plugins for MATLAB/Simulink and targeting integration with AFSIM, the solution will ensure that AI agents can operate effectively within DAF's preferred simulation platforms.
3.	Empowered and Committed DAF Customers: Mr. Kelly and Dr. Gump have agreed to assist in transitioning the proposed solution to a Phase III application, focusing on expanding its use within PEO Digital’s systems and exploring potential integration with AFSIM via existing commercial solutions or new developments.
4.	Joint and Non-DAF Government End-Users: The architecture we developed is also applicable to over 1,400 native DDS DoD applications, ensuring broad applicability across various defense platforms while maintaining compliance with ITAR restrictions and enabling collaboration on a global scale.
5.	Customer Memorandum: A Customer Memorandum detailing these engagements and commitments has been prepared and will be included in the “Letters of Support” section in Volume 5, Supporting Documents, as mandated by the proposal requirements. This document confirms the support and commitment of both end-users and customers to the project's next phase and ensures compliance with DAF requirements.
This section integrates the results from the Phase I feasibility study with detailed descriptions of user engagement, showing how RTI's proposed solution meets specific DAF end-user needs and aligns with strategic goals.
1.6	Compliance and Regulatory Activities
This project will not involve any of the listed compliance or regulatory activities.
1.7	Phase II Technical Objectives and Key Results 
Our goal in Phase II is to design, develop, demonstrate, and deliver a fully functioning GENESIS product baseline with end-to-end capabilities, including supporting the integration of AI agents in the MATLAB/Simulink simulation environment (AFSIM integration is targeted for post-Phase II).  As discussed above, we are extending our TRL-9 distributed communications framework, RTI Connext DDS –the following five objectives address the capability gaps that are needed for the implementation of the GENESIS distributed agent framework features:
Objective 1: Develop Comprehensive State Monitoring and Interaction
Achieve comprehensive state monitoring and semantic-level interaction among AI agents using the Object Management Group Data Distribution Service (OMG DDS) and RTI Connext DDS.
Key Results:
-	Develop and validate tools for semantic analysis of agent interactions, measured by the system's ability to accurately interpret and analyze the context of communications.
-	Implement logging and review mechanisms for agent interactions, with success measured by the system's ability to provide a complete and accessible audit trail.
-	Demonstrate real-time monitoring capabilities in a test environment, achieving 100% accuracy in detecting and reporting agent states.
Objective 2: Develop Multi-faceted Security Environment
Enhance the security of AI agent interactions through a multi-faceted security environment leveraging RTI Connext DDS’s existing security mechanisms and additional semantic controls.
Key Results:
-	Implement fine-grained access control policies and validate their effectiveness in restricting data and service access to authorized agents only.
-	Integrate semantic controls to monitor the content of communications, with success measured by the reduction of inappropriate or harmful (inadvertent or malicious) interactions as detected by the system. 
Objective 3: Develop Seamless Integration with MATLAB/Simulink Simulation Environment
Develop a seamless integration of the distributed AI framework with MATLAB/Simulink, with a transition plan for follow-on integration with AFSIM.
Key Results:
-	 Successfully implement and test the MATLAB/Simulink plug-in, measured by the seamless execution of complex scenarios involving AI agents and Simulink models.
-	Demonstrate the interoperability between AI agents and simulation models in MATLAB/Simulink, achieving 100% successful integration in test cases.
-	Complete the initial integration plan for AFSIM, with sign-off from AFSIM stakeholders.
Objective 4: Develop a Collaborative AI Environment
Create a collaborative AI environment that mirrors a human workplace (agents can discover and request services from authorized agents, humans, or data), enabling dynamic and effective interaction among AI agents.
Key Results:
-	Implement the DDS-based communication framework and measure its effectiveness in facilitating real-time data exchange between agents, achieving 100% message delivery.
-	Develop tools that enable collaborative task planning, execution, and evaluation, with success measured by agents' improved performance on complex tasks.
-	Ensure seamless data sharing between agents, with success measured by the accessibility and relevance of shared information in collaborative scenarios.
Objective 5: Develop and Demonstrate Inter-Agent Library
Develop libraries for direct communication over DDS in Python, C#, and JavaScript, ensuring seamless interoperability between AI agents developed using different frameworks and technologies.
Key Results:
-	Develop and validate communication libraries for Python, C#, and JavaScript, achieving seamless inter-agent communication.
-	Conduct 3 or more demonstrations during Phase II to stakeholders and potential customers, gathering feedback and achieving sign-off on the functionality and performance of the libraries.
-	Validate (via operational testing) that the libraries support direct communication over DDS, adhering to the DDS standard and QoS policies.
Anticipated Stakeholder Interaction
In Phase II, we will engage (ideally at least) monthly with our DAF stakeholders and other simulation teams. RTI has extensive lab facilities and the expertise to build out representative testing environments (e.g., using AWS GovCloud) for developing and evaluating GENESIS. We will not need clearances or waivers during Phase II.
Required/Aligned Stakeholders:
- DAF PEO Digital (TPOC) and CMSO MS&T engineers will ensure alignment with DAF/CMSO needs.
- MathWorks engineers to de-risk integration with MATLAB/Simulink (see letter of support from Mathworks)
These interactions will ensure that the project meets all necessary regulatory and operational standards and incorporates feedback from key stakeholders throughout the development process.
2	Phase II Work Plan (Non-Proprietary)
We are proposing a 21-month Phase II effort.  Dr. Jason Upchurch will be the Principal Investigator for this effort.  The effort will be entirely executed by RTI using RTI-managed facilities.  We will meet internally at least bi-weekly and hold monthly TIMs with our stakeholders. 
The main goals of their involvement in this project are to provide government representation, subject matter expertise, requirements, metrics for evaluation of the developed capability, and if successful, to eventually facilitate the adoption and transition of this capability into the Air Force.  Post-Phase II, we may need program-specific security clearances to support the integration of our technology into AFSIM.
RTI will focus on stakeholder engagement, requirements identification, software design and implementation. We will actively engage with our stakeholders, especially in the first few months, to gather and evaluate any additional requirements, and incorporate them into our software architecture process.  We will use agile development processes to rapidly derisk our standard software development processes to ensure the quality of the generated products.  
The output of our Phase II will include relevant documentation (Requirements, Software Design, etc.), a baseline GENESIS implementation, and a demonstration of its capabilities. In addition, we will provide quarterly status reports, a final report, and a Phase II summary report.
2.1	Scope 
Our Phase II effort will focus on addressing all four identified objectives described in Section 1.7.  On the surface, this might appear to be overly ambitious; however as listed in Section 10, we have already been extensively engaging in related work.  Our scope takes this knowledge and experience into account.  The PI has over 12 years of experience in R&D and 22 years of working with the Air Force in various capacities as well as leading the feasibility effort for this project.  He is confident that we will successfully execute on this effort.
Our proposed Phase II effort will focus on: de-risking, identifying suitable technologies, demonstrating foundational capabilities, and evaluating the suitability of the overall GENESIS prototype for DAF simulation needs.
2.2	Task Outline
In order to accomplish our proposed objectives, we have defined the following eleven tasks:
Task 1: Requirements and Metrics Capture (months 1-2)
Objective: Gather detailed requirements and define key performance indicators (KPIs) for the project.
- Task 1.1: Conduct workshops and meetings with stakeholders to gather detailed requirements.
- Task 1.2: Define key performance indicators (KPIs) and metrics for the project.
- Task 1.3: Document requirements and metrics for future reference and validation.
Outcomes: A comprehensive set of requirements and defined KPIs, providing a clear foundation for the project's development and evaluation.

Task 2: Driving Simulation Use Case Down-Select, Definition, and Functional Decomposition (months 3-4)
Objective: Identify and evaluate potential simulation use cases and define them in detail.
- Task 2.1: Identify and evaluate potential simulation use cases for the implementation of the Distributed AI Framework in the MATLAB environment.
- Task 2.2: Select the most relevant and impactful use cases for further development.
- Task 2.3: Define the selected use cases in detail, including functional requirements and expected outcomes.
- Task 2.4: Decompose the system into functional components to guide development and integrations.
Outcomes: A detailed definition and functional decomposition of the selected simulation use cases, ensuring clarity and direction for subsequent development tasks.

Task 3: Early Prototype Refinement (months 5-6)
Objective: Refine the early prototype architecture and address any technology gaps.
- Task 3.1: Evaluate the approach of our early work on distributed AI agents for technology gaps in the base framework.
- Task 3.2: Conduct a data modeling analysis for basic messaging structures and methods for inter-agent communication and discovery.
- Task 3.3: Refine the early prototype architecture to enable the development of advanced features of the framework.
- Task 3.4: Implement the basic framework to provide inter-agent communication over DDS.
Outcomes: A refined prototype that addresses identified technology gaps and supports inter-agent communication.

Task 4: Inter-agent Library Design & Implementation, Demonstration (months 7-10)
Objective: Develop and demonstrate the initial inter-agent communication library.
- Task 4.1: Select initial library language and agent framework for the first demonstration based on customer feedback.
- Task 4.2: Implement the initial library based on the target architecture.
- Task 4.3: Prepare and conduct a demonstration of the initial architecture to stakeholders, gathering feedback for further refinement.
Outcomes: A functional inter-agent communication library demonstrated to stakeholders, providing a basis for further refinement.

Task 5: Simulink/MATLAB Use Case Integration (months 11-12)
Objective: Integrate the distributed AI framework with MATLAB/Simulink and plan for AFSIM integration.
- Task 5.1: Work with stakeholders to ensure that targeted use cases are still highly relevant.
- Task 5.2: Refine the architecture based on feedback from demonstrations to stakeholders.
- Task 5.3: Architect the use case with the refined distributed AI agent architecture.
- Task 5.4: Design and implement any needed agents for the targeted use cases within the Simulink/MATLAB environment.
Outcomes: Successful integration of AI agents with MATLAB/Simulink, with a plan for subsequent AFSIM integration.

Task 6: Architecture Refinement, Security Access and Dataflow (months 13-14)
Objective: Enhance the security and dataflow aspects of the framework.
- Task 6.1: Analyze data flow of the demo architecture for threat modeling using STRIDE.
- Task 6.2: Analyze access requirements for the security layer using STRIDE threat modeling.
- Task 6.3: Implement an access model using DDS Security.
Outcomes: A robust security model ensuring safe and secure inter-agent communication and dataflow.

Task 7: Agent Service Registry Design, Implementation, and Demonstration (months 15-16)
Objective: Develop and demonstrate the agent service registry.
- Task 7.1: Analyze and select target agent frameworks based on state-of-the-art agent frameworks in the market.
- Task 7.2: Evaluate any changes to mechanisms and messaging requirements for inter-agent communication between heterogeneous frameworks.
- Task 7.3: Architect an agent service registry into the distributed AI agent framework.
- Task 7.4: Prepare and conduct a demonstration of the current architecture within the driving use case to stakeholders, gathering feedback for further refinement.
Outcomes: A functional agent service registry demonstrated to stakeholders, facilitating inter-agent communication across diverse frameworks.

Task 8: Semantic Security Service Layer, Design, & Implementation (months 17-18)
Objective: Develop a semantic security layer to enhance interaction safety.
- Task 8.1: Refine architecture based on feedback from stakeholders.
- Task 8.2: Evaluate semantic security requirements based on STRIDE and error states.
- Task 8.3: Design and implement a semantic security agent targeting input/output evaluations.
- Task 8.4: Incorporate semantic security evaluations into endpoint library architecture and agent service registry.
Outcomes: A semantic security layer integrated into the framework, enhancing the safety and reliability of AI agent interactions.

Task 9: Multi-Agent Framework Library Development & Demonstration (months 12, 21)
Objective: Develop and demonstrate communication libraries for multiple agent frameworks.
- Task 9.1: Work with stakeholders to ensure that targeted agent frameworks for inter-agent communication are still relevant.
- Task 9.2: Implement final library for target agent framework #1.
- Task 9.3: Implement final library for target agent framework #2.
- Task 9.4: Implement final library for target agent framework #3.
Outcomes: Completed communication libraries for multiple agent frameworks, demonstrated and validated through stakeholder feedback.

Task 10: Documentation
Objective: Create comprehensive documentation for the distributed agent framework and libraries.
- Task 10.1: Create documentation for the distributed agent framework, including security and agent registry.
- Task 10.2: Create documentation for agent framework library integration for target agent framework #1.
- Task 10.3: Create documentation for agent framework library integration for target agent framework #2.
- Task 10.4: Create documentation for agent framework library integration for target agent framework #3.
Outcomes: Comprehensive documentation that supports the deployment, integration, and usage of the distributed agent framework and communication libraries.

Task 11. Project Management. We will utilize standard project management practices to coordinate the oversight and successful execution of this project.  We will engage with the AFRL USAF CMSO, PEO Digital, and MathWorks, setting up a tempo for interaction within the first month of execution.  We will manage the timely delivery of reports, updates, and milestones.  We will also manage requirements gathering for the subsequent tasks.
Outcomes: Reports and overall successful progress against schedule/milestones/deliverables. 

Agile Practices: Where applicable, we will use agile spiral-based development practices, and share documentation and test results. This iterative approach will ensure continuous improvement and stakeholder engagement throughout the project.
2.3	Milestone Schedule (Non-Proprietary)
Task	Exp. Delivery	Deliverable	Acceptance Criteria	Payment Amount
Milestone 1
Complete Task 1: Requirements Capture 	CA + 2	Documentation of completed requirements analysis and metrics	Documented results were reviewed and determined acceptable by DAF end-user and customer.	$75,000 
Milestone 2
Complete Task 2: 
Use case and functional decomposition	CA+4	Use case and functional decomposition documentation	Documented results were reviewed and determined acceptable by DAF end-user and customer.	$137,500


Milestone 3
Complete Task 3: 
Early Prototype Refinement	CA+6	Report and detailed documentation on revised prototype architecture	Documentation and presentation were reviewed and determined acceptable by DAF end-user and customer.	$137,500


Milestone 4: 
Complete Task 4:
Agent Library design, implementation, & demonstration	CA+8	Documentation and demonstration of completed library demo
	Documentation and presentation were reviewed & determined acceptable by DAF end-user and customer.	$137,500


Milestone 5
Completed Task 5: Simulation Environment Use Case Implementation and Demonstration	CA+10	Documentation of completed simulation environment integration
	Documentation and demonstration were reviewed & determined acceptable by DAF end-user and customer.	$137,500


Milestone 6
Complete Task 6: 
Security Access Controls	CA+12	Documentation of security access layer for framework 	Documentation and demonstration were reviewed & determined acceptable by DAF end-user and customer.	$137,500


Milestone 7
Complete Task 7: 
Agent Service Registry	CA+14	Documentation and demonstration of framework agent service registry	Documentation and demonstration were reviewed & determined acceptable by DAF end-user and customer.	$137,500


Milestone 8
Task 8 Completed: 
Semantic Security	CA+16	Documentation and demonstration of semantic security controls in the framework 	Documentation and demonstration were reviewed & determined acceptable by DAF end-user and customer.	$137,500


Milestone 9
Complete Task 9: 
Multi Agent/Language Framework library development	CA+18	Documentation and demonstration of completed framework with heterogeneous agent integration. Final Customer Review Meeting, Evaluation Assessment Report, Demonstration, and next-Phase Development Plans	DAF customer / end user agree that the evaluation, demonstration, and final report were acceptable.	$137,500


Milestone 10
Documentation and Completed Final Report	CA+21	Final Report, including final proposed updates to the framework and individual libraries	DAF customer / end user agree that the final report was acceptable.	$75,000

2.4	Deliverables
We plan to provide the following deliverables:
●	Reports: Quarterly Status, a Final (at the end of month 21), and a Phase II Summary
●	GENESIS Software Requirements and Design Documentation (at the end of the effort)
●	The milestones identified above
●	We will also provide two intermediate and one final demonstration of GENESIS 
3	Commercialization Strategy
3.1	Company Information
RTI specializes in creating standards-based infrastructure software for safe and secure data distribution between heterogeneous systems across different industries. Our flagship product is the leading implementation of the OMG DDS specification (by volume, sales and market share). RTI also generates revenue through training, consulting, and expert engineering services. RTI has completed over 50 federally funded projects over the last 20 years and has a 100th percentile Commercialization Achievement Index (100%), placing RTI in the top 1% of companies for efficiency in transitioning/commercializing SBIR/STTR technology. RTI has no foreign investment, but many foreign paying customers. RTI sells to major system integrators and complies with US regulatory requirements.

RTI's SBIR commercialization achievement index (CAI) of 100 indicates that we are in the top 1% of all SBIR-funded companies to transition our research to product.

3.2	Customer and Competition
Clear description of key technology objectives: See section 2.5: Phase II Technical Objectives
Current competition and advantages compared to competing products or services. We currently do not have competition – our solution is a unified framework that will enable the integration of, and interactions between, existing agent frameworks. Our solution will provide four distinct market advantages: 1) A standardized communication interface for communication between agents and DAF M&S systems; 2) A pluggable agent inter-agent communication framework, with discovery of agents and services built in; 3) A secure framework with access controls (agents, services, humans) and semantic controls (monitor messaging and intercept deviant messaging); 4) GENESIS will use military-proven technology.
Description of hurdles to innovation acceptance.  The biggest hurdle to acceptance will be the successful integration into AFSIM.  Once integrated, it will be supported by PEO Digital and the AFSIM team.
3.3	Market
Technology demonstration events at Phase II completion will mark a major milestone, providing evidence of the viability and efficiency benefits of the GENESIS Distributed Agent Framework. Defense and Defense Modeling, Simulation and Training are in RTI’s highest growth market segments, with over $150M in addressable market.  Customers often take one or more years to evaluate technologies before purchasing. RTI currently has around 10-15% penetration, which we hope to double over 3-5 years. RTI has an established in-house aerospace and defense sales and marketing teams with a global distribution model to increase market awareness and market share. In addition, while GENESIS targets the simulation market in the Phase II effort, PEO Digital, AFRL, and RTI are confident that the technology is foundational and will have broad applicability wherever multi-agent intelligence is desired.
3.4	Intellectual Property (IP)
RTI maintains a patent portfolio and has full-time legal staff to defend our IP. RTI invests heavily in R&D, testing, and external certification to keep our competitive advantage. 
3.5	Financing
RTI plans to seek additional DoD funding for the maturation of GENESIS. Once we have productized it, we will utilize IRAD investments to continue to maintain and to evolve it to address our customers' needs.
3.6	Assistance and Mentoring
Q: What is the first product into which GENESIS will be incorporated? A: Initially, Mathworks Simulink; integration with AFSIM is planned as a post-Phase II effort – assuming the Phase II effort is successful.
Q: Who are the customers and what is the estimated market size?  Customers desiring solutions that will simplify the development and deployment of Generative AI technologies is growing exponentially at this point.  GENESIS is focused on customers building out larger AI-based solutions and not one-off applications.  This market includes many of our commercial and defense customers.  The total U.S. AI market is $42B in 2023 and is growing rapidly. AI integration is a non-trivial part of that.  We conservatively estimate the market for this specific solution to be $100M/year or more today and growing rapidly. 
Q: How much money is needed to bring GENESIS to market? To fully mature the initial version of this technology we believe it will require $5M-$10M. How will the funding be raised?  We will target PEO Digital/AFLCMC and STRATFI.  On the corporate side we plan to seek STRATFI matching funds to work with Mathworks to continue the maturation of GENESIS for Simulink.  Closer to the end of Phase II we will also engage with several other RTI customers to seek investment.
Q: Does the company possess marketing expertise? If not, how will it be obtained?  A. RTI has full-time professional sales, business development, product management and marketing communications staff in-house. RTI also has media, graphic design, and public relations consultants.
Q: What companies are your competitors, and what is the firm’s price and/or quality advantage over them?
A. There are no competitors that offer a comparable framework. We will be developing a first-in-class solution.  Competitors offer agent framework solutions for developing unsecured, non-standards-based agent applications that are not scalable. Regarding our foundation technology, RTI maintains its 70% market leadership position through an unmatched combination of investment in software quality and testing, documentation, tools, training, and engineering support, along with external certifications.
Q: Are there private sector or non-SBIR/STTR funding sources demonstrating commitment to Phase II results?  A: We have strong interest from Mathworks, but it is too early for their financial commitment until we demonstrate its capabilities in Simulink.
Q: Has your company received, or will it receive any foreign investment? If so, what is the source and the received or anticipated amount? A: Our company has not received, nor are we pursuing, any foreign investment.
Q: Are there Phase III (Government or commercial) follow-on commitments for the proposed technology?
A. No hard commitments. However, we worked on the vision and scope of this effort with our end customer and end user, so it is fully aligned with the interests of PEO Digital and CMSO.
Q: Are there any other commercial potential indicators? Consider pre-sales, pilots, sales, revenue, active users, subscriptions, downloads, and/or other forms of traction/adoption and commercial signals of interest, demand, and faith in your team/solution.  A: As a commercially successful company, RTI has a strong customer base that would serve as our target market.  In addition, the AI agent market is growing exponentially, which we take as solid evidence of the market potential.
Q: What is the last 12 months’ total revenue from non-Defense commercial solution sales?  A. RTI has had approximately $12M in revenue from non-Defense commercial sales from our existing products.
Q: State the proposed Phase II’s anticipated end results, specifically plans to transition to a Phase III with a potential Government customer.  A.  We plan to design, develop, and deliver an open, modular, scalable, secure, and resilient distributed agent framework integrated with Mathworks Simulink.  As a next step, our PEO Digital customer wants us to integrate with the AFSIM training simulation framework (funded by STRATFI/Phase III funding).
Per directions, our transition strategy is detailed in Section 9 of the Customer Memorandum.
4	Military Applications/DoD Customers 
Due to the incredible commercial capability demonstrations we continue to witness as generative AI rapidly evolves, there is significant potential for widespread DoD interest and adoption of the GENESIS technology.  As noted in Section 1, GENESIS would be the first modular, secure, scalable, self-discovering, distributed agent framework on the market.  The applications of this generalized agent framework are truly unbounded.
Our stakeholders, PEO Digital and CMSO, helped provide the requirements for GENESIS with the intent to first use it for 1) improving outcomes and lowering the cost of training, and 2) as operational assistants to improve operator performance and effectiveness.
If successful, our CM stakeholders would like to see GENESIS transitioned to integrate with AFSIM in a follow-on phase. Like most DAF groups, they do not have available 2024 funds.  However, we anticipate program funding for transition in 2026 once the Phase II has ended.
5	Foreign Persons
Not Applicable.
6	Key Personnel
Also see attached resumes in Volume 5.
Jason Upchurch, PI. Dr. Upchurch, a cleared (TS) U.S. citizen, is a Principal Research Engineer on the RTI Research Team. His current research interests are Generative AI agents, AI security, secure distributed systems, and cyber information propagation and analysis.  His work in distributed agent frameworks is the basis for this proposal.  He has served in a leadership role in two DAF laboratories focusing on government and commercial collaborative projects.  He has successfully managed over $7M in SBIR and other USG funded research projects.  He earned his Ph.D. in Engineering Security from the Department of Computer Science, University of Colorado, Colorado Springs in 2016.
Paul Pazandak, Project Manager. Dr. Pazandak, a cleared (TS) U.S citizen, is the director of RTI's Research Team.  He oversees the acquisition and successful execution of research at RTI. He has participated on and has led government-funded and commercially funded military research for over 30 years. Relevant to this proposal, he has hands-on experience with neural networks, machine learning, and generative AI.  He has successfully managed the execution of over 50 SBIR Phase I/II research projects along with the technology transition to the product teams.
Kyle Benson. Dr. Benson, a U.S. citizen, is a Senior Research Engineer on the RTI Research Team. He completed his Ph.D. in Computer Science at the University of California, Irvine immediately prior to joining RTI in 2019. He has proposed, won, executed on, and led multiple SBIR/STTR research projects (both Phase I/II) since then. Relevant to this proposal, he has hands-on experience with generative AI and machine learning application and testing.
7	Non-Defense Commercial Customers
We have had over $12M/yr in non-defense sales of the product we propose to enhance.  While military systems have the strongest need for large-scale agent integration and testing frameworks, we are also seeing a few large RTI customers (like GE Healthcare) moving in this direction for their critical systems.  Given the benefits of GENESIS as an early warning indicator during a large-scale integration effort, we expect many of our customers will adopt these practices.  While this does not guarantee future success, RTI does have an established revenue channel for sales.
At this time, we anticipate that the resulting extensions to our commercial solution will be incorporated into our existing products, and that they will be included at no additional charge to our defense and industrial customers.  We believe that they will contribute market-driving features that will provide added discriminators, resulting in more sales. Few other companies can provide this level of return on DoD R&D investments.
8	Investors and Partner
None.
9	Related Work
•	RTI possesses global-leading expertise in helping customers build open, modular systems using RTI’s implementation of the OMG DDS standard to include the world’s largest SCADA system, a scalable, safe, secure, reliable distributed solution for hospitals, the world’s largest wind farm, DoD C2, DoD Fire Control, and more than 1700 other critical commercial systems.  We have more than 50 successful SBIR Awards for distributed systems with the highest possible commercialization index.  RTI’s role as a global leader in distributed system communications is firm.
•	RTI has recently conducted work under SBIR funding for state monitoring of DDS systems to detect distributed system errors and attacks (Accelerating Threat and Risk Detection within Data Centric Networks, DAF Phase II: FA864923P1171: kevin.kelly.34@us.af.mil) that is directly related to our “Safe” monitoring task in this proposal.
•	The PI for this project not only conducted the feasibility study for this project but conducted a multi-year machine learning project to optimize malicious software detection in a joint effort between USAFA, DHS, and Intel Corporation in addition to managing the USAFA Anti-Malware Laboratory (USAFA Anti-Malware Laboratory: Malware Provenance: Gregory.bennett@afacademy.AF.edu). 
10	References
[1]  The Data Distribution Service Specification, v1.2, http://www.omg.org/spec/DDS/1.2/
[2]  The Data Distribution Service Security Specification, https://www.omg.org/spec/DDS-SECURITY/
[3] OSD UAS/UCS Control Segment Executive Brief (unclassified), “The Data Distribution Service – Reducing Cost through Agile Integration”, Executive Summary 2011.
[4] The RTI Connext QoS Reference Guide, v7.0, 2022, web link
[5] MathWorks and RTI Connext DDS Blockset Integration, web link
[6] RTI Technology Partners, https://www.rti.com/company/partners
