Great, I’ll gather a comprehensive analysis of DroneUp with an emphasis on their partnerships, regulatory compliance status, and real-world demo capabilities in trusted autonomous drone operations. I’ll also look into how their ROS2 foundation might support DDS bridging (particularly with RTI Connext DDS), and explore how they might align with your GENESIS architecture for AI-driven digital twin simulation and deterministic execution. I’ll include their history with government or DoD contracts, with a focus on autonomy and AI initiatives.
I’ll let you know as soon as the findings are ready.
Assessing DroneUp for a DoD-Funded Autonomy Research Partnership
DroneUp’s Government and Defense Partnerships
DroneUp has established notable partnerships in the defense and public sector ecosystem. On its website, the company prominently lists collaborations with major defense organizations – including NATO (North Atlantic Treaty Organization), the U.S. Navy, U.S. Air Force, Naval Warfare Development Center, and the Department of Defense. One high-visibility example was a partnership with NATO’s Allied Command Transformation (ACT): in September 2020, DroneUp and NATO ACT’s Joint Force Development conducted an autonomous last-mile resupply experiment in Virginia to prove battlefield drone delivery concepts. This NATO experiment successfully demonstrated pilotless drone deliveries of unique payloads to multiple recipients under field conditions, with drones autonomously locating the recipients and confirming delivery – all without human intervention in flight. Such collaboration underscores DroneUp’s role in trusted autonomy trials for military logistics.
Beyond NATO, DroneUp has engaged with U.S. government initiatives in autonomy and airspace integration. It was a key industry partner in a USDOT “SMART” grant project (Strengthening Mobility and Revolutionizing Transportation) to improve rural healthcare access via drones. In early 2024, DroneUp, alongside the Virginia Institute for Spaceflight & Autonomy (VISA) and local agencies, demonstrated medical deliveries by drone to remote communities (e.g. Virginia’s Tangier Island) as part of this DOT-funded program. The demonstration – attended by DOT’s Chief Scientist – highlighted DroneUp’s ability to work in a multi-stakeholder, federally funded autonomy project, showcasing drones delivering medications over a 17-mile Beyond Visual Line of Sight (BVLOS) flight to a rural clinic. This exemplifies DroneUp’s experience collaborating with government, academia, and healthcare partners on trusted autonomous systems in real-world scenarios.
DroneUp also partners within the wider autonomy ecosystem to enhance its technology. For instance, it teamed with Iris Automation (a specialist in AI-based detect-and-avoid) to deploy Casia G ground-based sensors for airspace awareness in its BVLOS delivery operations. By networking optical detection nodes, DroneUp can receive automated alerts of intruding aircraft and safely maneuver drones – a capability that aligns with DoD’s emphasis on airspace deconfliction and safety. Additionally, DroneUp announced a strategic partnership with Volatus Aerospace (Canada) to expand cargo drone services across North America. This partnership leverages DroneUp’s U.S. regulatory approvals and traffic-management tech alongside Volatus’s cargo drone platforms. In summary, DroneUp has woven itself into a network of government agencies, defense stakeholders, and autonomy technology partners, which bolsters its credibility as a potential DoD research collaborator.
Regulatory Compliance and Credentials for DoD Operations
DroneUp has achieved key regulatory milestones that demonstrate its compliance with U.S. aviation rules – a critical factor for any DoD-related project. Notably, in late 2024 DroneUp became one of only six U.S. drone operators to secure an FAA Part 135 Air Carrier certificate. This Part 135 certification (under FAA Part 119) authorizes DroneUp to operate as an unmanned air carrier for commercial deliveries, enabling routine beyond-visual-line-of-sight (BVLOS) flights over populated areas with FAA oversight. Achieving Part 135 is significant – it required DroneUp to meet stringent safety, training, maintenance, and operational standards on par with airlines. DroneUp proudly notes it was the fastest drone company to attain Part 135 certification on a new platform, reflecting a strong compliance culture. The company also implements a Continuous Airworthiness Maintenance Program (CAMP) for its drone fleet, ensuring DoD-level rigor in maintenance and reliability.
In addition to Part 135, DroneUp holds a landmark FAA BVLOS waiver for drone delivery. In January 2024, the FAA approved DroneUp to conduct BVLOS operations for medical supply deliveries – making DroneUp one of the few U.S. companies with such authorization. This waiver allows DroneUp’s drones to fly beyond the pilot’s direct line of sight without visual observers, greatly expanding operational range. The initial approval supported deliveries at Riverside Health System facilities and paved the way for broader BVLOS deployments nationwide. DroneUp’s CEO noted that achieving BVLOS approval validated their safety processes and technology and unlocks true autonomy and scale for their operations. For DoD purposes, these regulatory credentials indicate DroneUp can legally perform advanced autonomous flights in U.S. airspace, including complex scenarios like long-range or swarm operations under regulated conditions.
DroneUp’s compliance extends to airspace integration and security requirements important to defense. The company emphasizes a “zero-trust” cybersecurity framework and encrypted data links in its Uncrewed Traffic Management solution. Its Uncrew™ UAS traffic control system is designed for seamless multi-agency integration (FAA, DoD, DHS, etc.) to enable unified command of airspace. Furthermore, DroneUp’s hardware and software are American-made and NDAA-compliant, aligning with DoD restrictions against foreign drone components. By unifying safety, security, and compliance credentials – from FAA authorizations (Part 135, BVLOS) to cybersecurity and maintenance standards – DroneUp positions itself as a trusted, regulation-savvy partner for DoD-funded autonomous operations.
Experience with Real-World Autonomous Flight Demos
DroneUp has a proven track record of executing real-world demonstrations of autonomous drone capabilities, often in high-stakes or “trusted autonomy” contexts. As mentioned, DroneUp’s work with NATO’s autonomous resupply experiment in 2020 showcased a fully autonomous drone delivery to military end-users. In that trial, soldiers in the field simply pressed a button to summon a drone, which then autonomously flew to their location (even if the soldier was moving) and delivered a payload, before returning to base. The system accurately identified recipients and dropped the correct supplies with no pilot control, underscoring DroneUp’s ability to demo trusted autonomous behavior (target identification, navigation, and delivery) in a mission-like environment. This kind of hands-on experimentation with military stakeholders (including special operations teams) indicates DroneUp can support and execute complex demo scenarios required by DoD research programs.
In the civilian sector, DroneUp has also conducted large-scale operational tests that validate its autonomous systems. At its R&D facility in Virginia (Richard Bland College), DroneUp achieved a milestone of 500 drone deliveries in a single day as of August 2024. This stress-test involved automation of the entire delivery process to push throughput and prove scalability. Notably, DroneUp improved its pilot-to-drone ratio to a “one-to-many” control model, demonstrating that a single operator could oversee numerous simultaneous autonomous flights safely. Such feats required reliable autonomy (for navigation, takeoff/landing, and payload handling) and were made possible by DroneUp’s “Uncrew” software platform automating flight plans and airspace deconfliction. The results – 40 deliveries per hour with up to 20 concurrent missions per operator – highlight DroneUp’s experience in coordinating multi-UAV operations in real time.
DroneUp has similarly showcased its tech in public safety and healthcare demos, building trust in autonomy. In October 2024, it completed Stage 1 of a “Medicine-by-Drone” pilot on Tangier Island, VA, flying prescription supplies 17 miles BVLOS to a remote clinic. The successful demo (part of the DOT SMART project) proved that autonomous drone logistics can meet critical needs in austere conditions, earning praise from local officials and federal observers. DroneUp also performs regular real-world delivery operations (e.g. retail deliveries with Walmart in multiple states), which have served as living “demonstrations” of integrating autonomy into everyday commerce. Through these varied experiences – from military exercises and government pilots to high-volume commercial ops – DroneUp has shown the capability to plan, execute, and support live autonomy demonstrations. This background would be invaluable for a DoD research project that requires field experiments or technology showcases.
Technical Architecture: ROS2, DDS, and Interoperability
While DroneUp’s specific use of ROS 2 (Robot Operating System) or DDS middleware isn’t explicitly advertised, the company’s technology approach suggests a strong foundation for interoperability and DDS integration. DroneUp describes its core platform as a “groundbreaking interoperability layer” that allows any autonomous system to communicate and coordinate, regardless of manufacturer or protocol. In practice, this means DroneUp’s software can bridge between different control protocols and data formats – a design philosophy very much in line with DDS (Data Distribution Service) principles of decoupled, real-time messaging. DroneUp’s Uncrew™ platform is a cloud-based system managing drone missions with real-time geospatial data, and it already ingests data from external sources like UTM (unmanned traffic management) feeds. This indicates DroneUp’s system can publish and subscribe to dynamic airspace data and telemetry, analogous to how a DDS bus operates.
Given that ROS 2 uses DDS as its underlying communication layer, any ROS 2-based autonomy solution will rely on DDS for data exchange. DroneUp’s emphasis on open integration and protocol-agnostic design strongly implies that interfacing with a DDS-based framework (such as RTI Connext DDS) would be feasible. In fact, DroneUp’s platform likely already addresses challenges like multi-node communication, real-time updates, and secure data distribution – all core aspects of DDS. For example, DroneUp highlights its secure communication infrastructure with fully encrypted data links and redundancy, which could map onto DDS security features if integrated. Moreover, DroneUp’s goal of networking heterogeneous drones and sensors parallels the DDS goal of interoperability across systems.
While no public source confirms DroneUp uses ROS 2 internally, the company’s work with robotics and autonomy suggests familiarity with common robotic frameworks. DroneUp has collaborated with academic partners (e.g. Embry-Riddle Aeronautical University and others) on UAS programs, which may involve ROS-based development. Even if their flight software is proprietary, their stated architecture could bridge to ROS 2/DDS environments via custom translators or DDS adapters. In summary, DroneUp’s technical stack is built for integration, which bodes well for incorporating RTI Connext DDS or implementing a ROS 2-to-DDS bridge in a joint project. Their “any protocol” interoperability claim signals that DroneUp can interface with external autonomy software and middleware, providing flexibility to a DoD research team leveraging GENESIS and Connext DDS.
Use of Digital Twins, AI, and Simulation in DroneUp’s Workflow
DroneUp’s approach to autonomy incorporates elements of AI-driven planning, real-time simulation, and possibly digital twin concepts – though often described in practical terms. The company’s Uncrew™ software employs AI and advanced algorithms for flight routing and coordination. On its U-ATM (Uncrewed Air Traffic Management) product page, DroneUp notes features like “Predictive routing” and real-time UAV deconfliction to ensure optimal airspace use. This implies an AI engine that can generate or adjust flight plans on the fly to avoid conflicts – essentially an adaptive autopilot intelligence. Indeed, DroneUp’s CTO has stated that Uncrew’s onboard intelligence lets drones autonomously decide on contingencies (e.g. emergency landings or returns) without pilot input. Such capabilities suggest AI-driven flight plan adaptation, where the drone or cloud system can simulate outcomes and choose the best course (a hallmark of trusted autonomy).
In terms of simulation and digital twins, DroneUp has engaged with partners to model and test complex scenarios. NASA researchers have worked with DroneUp to integrate its drone operations into NASA’s simulation and modeling efforts around UTM and autonomy. For example, NASA documentation from 2023 indicates plans for integration of DroneUp vehicles into NASA’s operational simulations, including projects like autonomous safe landing (Safe2Ditch) and wide-area hazard detection for drone overflight. This points to DroneUp contributing to or utilizing simulation-based evaluation of its drones for safety cases (e.g. finding emergency landing sites via a “digital twin” of the environment). Additionally, DroneUp’s high-rate delivery testing at RBC in Virginia likely relied on extensive simulation and digital twinning of operations to optimize throughput and safety before executing 500 flights/day. The press release notes they “rigorously performed capacity testing” on behalf of partners at that facility, which likely involved simulating mission workflows and ground logistics to reach the optimal pilot-to-drone ratio.
Furthermore, DroneUp’s software pipeline leverages advanced analytics and AI that align with digital twin approaches. The company highlights “AI-driven insights” for anomaly detection and pattern recognition in its technology offerings. This suggests they monitor drone operations in real time and compare against expected behavior (essentially a virtual model of how the system should operate – akin to a digital twin of the fleet’s performance). Their cloud platform uses real-time geospatial data and mapping, maintaining an up-to-date virtual picture of the airspace, which is fundamental to any digital twin of the operating environment. And by automatically generating mission plans from service requests and live data, DroneUp’s system is performing what could be seen as simulation-based planning – evaluating routes, weather, terrain, and air traffic data virtually to create an optimal flight plan. In essence, while DroneUp may not explicitly use the term “digital twin,” it employs the key ideas: virtual modeling of airspace and missions, AI-powered decision support, and simulation to validate autonomous behaviors. These capabilities would greatly benefit a research effort focused on autonomy, GENESIS simulation environments, and DDS messaging, as DroneUp can provide both the real-world data/vehicles and the virtual modeling expertise to iterate rapidly between simulation and live demos.
Programs and Contracts in Autonomous Operations and Airspace Integration
DroneUp’s trajectory has intersected with several programs and contracts aimed at autonomous operation, AI coordination, and low-altitude airspace integration. While much of DroneUp’s commercial fame came from retail drone delivery (e.g. its now well-known partnership launching Walmart’s drone delivery program in 2021), the company has increasingly aligned with government modernization initiatives:
Defense Innovation and Experiments: In addition to the NATO ACT trial, DroneUp has engaged with the U.S. Navy and Air Force on exploratory projects. The presence of the Naval Information Warfare/Development Center and USAF on its partner list hints at participation in exercises or CRADAs (Cooperative Research and Development Agreements). For example, DroneUp’s technology focus on swarm coordination and contested environment UAV management aligns with DoD interests in programs like the Air Force’s Collaborative Combat Aircraft (CCA) autonomy efforts. While DroneUp is not publicly named in CCA contracts (those went to defense primes), DroneUp’s capabilities in multi-UAV control could make it a candidate for future autonomy prototyping contracts.


Airspace Integration Initiatives: DroneUp has been involved in the broader push for low-altitude airspace integration, collaborating with FAA and NASA. It was not an official FAA IPP site lead, but through Virginia’s efforts (Virginia was an FAA UAS Integration Pilot Program participant), DroneUp contributed to state-level drone integration demonstrations. The company’s BVLOS operations and UTM connectivity position it well in the FAA’s BEYOND program goals (which extended IPP to tackle BVLOS and societal integration challenges). Moreover, DroneUp’s Uncrew™ U-ATC system is essentially tackling the next generation of UTM – providing real-time deconfliction, multi-agency coordination, and cybersecurity that basic UTM lacks. This suggests DroneUp is aligning with NASA/FAA research objectives to enable high-density drone ops in national airspace. Indeed, NASA has identified areas like ground risk assessment, automated emergency landing (Safe2Ditch), and detect-and-avoid where DroneUp’s operational data can inform standards.


State and Local Autonomy Programs: DroneUp’s work on the DOT SMART grant (Elevating Healthcare Access) is effectively a government contract for autonomy R&D. With ~$1.6M in funding (the SMART grant) split among partners, DroneUp’s role included flight testing, community engagement, and developing CONOPS for medical drone delivery. Similarly, DroneUp has received support from state innovation funds (VIPC in Virginia) to jump-start such projects. This shows the company’s ability to secure and execute publicly funded research programs, delivering results (e.g. reducing delivery times to remote areas) that meet contract objectives.


Autonomous Systems and AI Contracts: While not explicitly disclosed, DroneUp’s capabilities align with emerging DoD unmanned systems programs. For instance, the DoD’s focus on counter-UAS and airspace security (ref. initiatives by DIU and the recent DoD Counter-UAS strategy) creates opportunities for DroneUp’s airspace management AI. DroneUp’s Uncrew™ could be pitched as a command-and-control platform for coordinating friendly drones or swarms, and for integrating with counter-UAS systems (given its cybersecurity and multi-drone awareness features). Additionally, the company’s partnership with Doosan for hydrogen fuel cell drones in 2023 hints at work on long-endurance autonomous platforms, potentially useful for military applications (surveillance or persistent resupply).


In summary, DroneUp has shown itself to be an active participant in programs that shape the future of autonomous drone operations. Its blend of commercial delivery at scale, government-funded pilots, and defense-oriented demos attests to a versatility in meeting contract requirements. The company stays attuned to regulatory evolution and funding opportunities – from FAA waivers to SBIR-style collaborations – which makes it well-suited to partner on a 21-month DoD research project. DroneUp can bring to such a project proven technology (airborne and software), regulatory know-how, AI-driven autonomy, and a history of trust with government stakeholders, all of which would be critical for successfully using GENESIS simulation and RTI Connext DDS in advancing autonomous capabilities.
Sources:
DroneUp official website – Uncrew™ UAS Traffic Management and Partnerships


Brunswick County Economic Development – DroneUp Autonomous Last-Mile NATO Experiment (2020)


Dronelife news – NATO Drone Delivery Experiment (Sep 2020)


DroneUp Press Release – FAA Part 135 Certification (Dec 2024)


DroneUp Press Release – FAA BVLOS Waiver Approval (Jan 2024)


DroneUp Press Release – DroneUp Ecosystem & Autonomy (Mar 2024)


DroneUp Press Release – 500 Deliveries/Day & Uncrew Platform (Aug 2024)


DroneUp Press Release – $7 Drone Delivery Tech (Oct 2024)


DroneUp Press Release – Tangier Island Medical Drone Demo (Oct 2024)


DroneUp Press Release – USDOT SMART Grant Demo (Feb 2024)


DroneUp Technology Page – Interoperability and Secure Integration


Iris Automation News – Detect-and-Avoid Partnership (May 2023)


NASA (NTRS) – Notes on integrating DroneUp ops into autonomy simulations


GPT 4.5


Here's a detailed briefing to prepare you for your meeting with DroneUp's CTO, including clear objectives, proposed scope, timeline, and key action items. This will help DroneUp understand their potential role and integration points within the GENESIS framework for your Phase 2 trusted autonomy project.


DroneUp Meeting Preparation
Objectives of the Meeting
Clarify Partnership Role:

Define how DroneUp can integrate their Uncrew platform and ROS2-based drones into the GENESIS framework for a Phase 2 DoD-funded autonomy project.
Establish DroneUp’s responsibilities regarding real-world drone flight execution, integration testing, and demonstrations.

Technical Integration Discussion:

Discuss the potential for DDS bridging between GENESIS/RTI Connext DDS and DroneUp’s ROS2-based Uncrew system.
Explore DroneUp’s ability to interface their autonomous drones and UTM (Unmanned Traffic Management) systems with GENESIS’s agent-driven AI coordination and digital twin predictive capabilities.

Identify Demonstration Scope:

Agree on the scope of real-world flight demonstrations DroneUp can support in Phase 2.
Discuss leveraging GENESIS-generated, simulation-validated flight plans in real-world scenarios.

Discuss Regulatory & Security Considerations:

Confirm DroneUp’s current FAA regulatory compliance (Part 135, BVLOS waivers) suitability for DoD demonstrations.
Explore the implementation of GENESIS’s DDS-based semantic and transport security within DroneUp’s existing security frameworks.

Explore NVIDIA & Simulation Partnerships:

Discuss potential integrations with NVIDIA IsaacGym and simulations such as Gazebo or OneWorlding platforms to facilitate rapid digital-twin development, validation, and demonstration.


Proposed Scope of Effort (Phase 2)
Leveraging Phase 1 learnings and your GENESIS framework, the Phase 2 effort would focus on developing and demonstrating robust, trusted autonomous drone operations using generative AI-driven digital twins and dynamic flight planning, validated via simulation and executed through DroneUp's fleet:

Key Components of Proposed Scope:

Integration of GENESIS and DroneUp Uncrew:

Establish DDS-ROS2 bridging between GENESIS and DroneUp’s Uncrew.
Demonstrate real-time agent-driven decision-making, altering flight plans dynamically based on situational changes.

Digital Twin Development and Utilization:

Create digital twins of DroneUp’s drones and operational scenarios.
Employ generative AI within GENESIS to rapidly create, test, and validate flight paths and operational tactics in accelerated simulations.

Real-World Flight Demonstrations:

DroneUp executes real drone flights based on validated GENESIS-generated plans.
Use DroneUp’s autonomous drone fleet and existing UTM capabilities to demonstrate trusted autonomy, situational adaptability, and operational security.

Advanced Monitoring and Security Integration:

Integrate GENESIS’s semantic security and DDS transport-layer security within DroneUp’s operational framework, emphasizing secure, trusted communications.


Suggested Timeline (21-month Phase 2)
Milestone
Timeframe
Key Deliverables
Kickoff & Requirements Definition
Months 1-2
Integration plan with DroneUp finalized
DDS-ROS2 Bridging & Initial Integration
Months 3-5
Initial GENESIS-Uncrew bridge established
Digital Twin Development
Months 4-8
Digital twin model of drone operations
AI-Driven Flight Plan Generation
Months 6-10
Validated flight plan scenarios
Initial Real-World Demonstrations
Months 11-14
First flight tests with DroneUp drones
Advanced Scenario Testing & Validation
Months 15-18
Complex, dynamically adapting scenarios
Final Demonstration & Reporting
Months 19-21
Full capability demonstration and report



Action Items for DroneUp Discussion (AIs)
DDS and ROS2 Integration:

Discuss feasibility, timeline, and requirements for bridging DDS with DroneUp’s existing ROS2 Uncrew platform.

Real-World Flight Demo:

Confirm DroneUp’s capability and resources for executing GENESIS-driven flight demonstrations.
Identify practical scenarios DroneUp can immediately support.

Regulatory Compliance & Certification:

Validate DroneUp’s current FAA and DoD-compliance status.
Identify any regulatory or security hurdles anticipated in DoD-focused operations.

Simulation & NVIDIA IsaacGym Integration:

Gauge DroneUp’s interest/capability to integrate simulation tools like Gazebo, OneWorlding, or IsaacGym within their workflows.
Identify necessary technical support or collaboration with NVIDIA.

DoD Line-of-Sight (LOS):

Inquire if DroneUp has established relationships or recommended contacts within DoD or related agencies who could provide LOS or strategic alignment for demonstrations or project validation.


Suggested Discussion Points for CTO Meeting
Does DroneUp use models/sim today?
Are they interested in our approach?
Do they have any suggested modifications or enhancements?
Level of effort / involvement?  We need to determine how much… 
Do you have a killer app for DAF that we should focus on?
Can they provide drones for the demos?  If so, what types?
Do we want to add cameras/other sensors, or keep it simple?
We MUST define a clear CONOPS/use cases to motivate the DAF need.
delivery?
sensor payload?


What level of readiness does DroneUp currently have for DDS-based integrations?
Can DroneUp describe prior experiences integrating with external AI or simulation-driven frameworks?
What limitations or special considerations (technical, operational, or regulatory) does DroneUp foresee for supporting dynamic, AI-driven flight plans?
Does DroneUp have any DAF (or other) contacts that could provide an LOS



This structure will clarify DroneUp’s potential contributions and integration into your Phase 2 effort, streamlining your CTO discussion and aligning your visions effectively.
Considering the constraints (DroneUp cannot exceed 30% of the funding) and leveraging their strengths, here are specific, high-value tasks suitable for DroneUp in the partnership:
Recommended Tasks for DroneUp (Within 30% Funding Limit):

1. Real-World Flight Demonstrations and Execution
Justification: DroneUp has FAA Part 135 certification and extensive experience in BVLOS and autonomous drone operations.

Scope:

Execute real-world drone operations for all demonstrations.
Provide necessary drones, hardware, and flight crew support.
Operational logistics (site selection, setup, operational execution, and data collection).

Outcome:

Validate GENESIS-generated flight plans and AI-driven decision-making in live demonstrations.


2. Integration of Uncrew ROS2-based Autonomy Framework with DDS
Justification: DroneUp’s Uncrew platform, being ROS2-based, can feasibly bridge with DDS to demonstrate the technical interoperability of GENESIS and drone autonomy frameworks.

Scope:

Develop and validate ROS2-to-DDS bridging software modules.
Ensure secure integration using GENESIS DDS Security standards.

Outcome:

Achieve seamless integration enabling dynamic updates to drone operations in real-time.


3. Regulatory & Operational Compliance
Justification: DroneUp holds critical FAA certifications and compliance expertise, key to DoD and government operational standards.

Scope:

Ensure compliance with FAA and DoD regulatory frameworks (including flight permissions and BVLOS authorizations).
Document regulatory processes and lessons learned.

Outcome:

Smooth regulatory pathway ensuring legality and operational continuity.


4. UTM (Uncrewed Traffic Management) Integration
Justification: DroneUp’s existing UTM product aligns naturally with GENESIS’s needs for secure, coordinated autonomy.

Scope:

Integrate GENESIS decision-making and agent communications with DroneUp’s UTM platform.
Demonstrate GENESIS-driven drone coordination within congested or complex airspace scenarios.

Outcome:

Robust, integrated UTM demonstration showcasing GENESIS’s AI coordination capabilities.


5. Data Collection and Feedback Loop Support
Justification: DroneUp’s flight operations provide invaluable operational data for iterative development and validation.

Scope:

Collect flight telemetry, operational performance data, and flight logs during demonstrations.
Share structured data with GENESIS development team for iterative model tuning.

Outcome:

Enhance GENESIS’s predictive accuracy and digital-twin fidelity.


6. Support for Digital Twin Development
Justification: DroneUp’s drones and operations provide accurate real-world models for digital-twin simulations.

Scope:

Provide detailed specifications, sensor models, and flight profiles to accurately construct digital twins.
Validate GENESIS digital-twin simulations against DroneUp real-world operational data.

Outcome:

Accurate digital twins enhancing AI-driven predictive modeling and validation.


Funding Distribution Guidance:
Given DroneUp’s federal constraint (max 30%), these tasks effectively leverage their specialized expertise while meeting regulatory limits. A recommended approximate funding split within DroneUp's tasks:

Task
Recommended % (of DroneUp’s 30%)
Real-World Flight Demos & Execution
40%
Uncrew ROS2-to-DDS Integration
20%
Regulatory & Operational Compliance
15%
UTM Integration
10%
Data Collection & Feedback
10%
Digital Twin Development Support
5%



Summary of DroneUp's Primary Responsibilities:
Conduct all live drone operations and demonstrations.
Implement DDS bridging with GENESIS via ROS2/Uncrew.
Ensure and manage regulatory compliance and operational certifications.
Integrate GENESIS with DroneUp’s existing UTM system.
Provide operational data and feedback for continuous GENESIS optimization.
Support accurate digital-twin modeling for realistic simulation scenarios.

These well-defined tasks fully utilize DroneUp’s proven expertise and infrastructure, clearly aligning them within regulatory funding guidelines while maximizing their contribution to the overall success of the Phase 2 effort.




Modeling and Simulation of Large Scale Drone Deployment

https://vimeo.com/1066009602/1cf79ba58f?&signup=true#_=_


