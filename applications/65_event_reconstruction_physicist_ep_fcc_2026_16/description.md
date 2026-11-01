# Event Reconstruction Physicist (EP-FCC-2026-166-GRAP)

- **Institution**: CERN
- **Location**: Geneva, Switzerland (['Europe', 'Switzerland'])
- **Application Deadline**: 2026-11-13
- **Application Link**: [https://jobs.smartrecruiters.com/CERN/744000157404339](https://jobs.smartrecruiters.com/CERN/744000157404339)
- **InspireHEP Record**: [https://jobs.smartrecruiters.com/CERN/744000157404339](https://jobs.smartrecruiters.com/CERN/744000157404339)
- **Categories**: ['hep-ph', 'hep-th', 'quant-ph']

---

## Evaluation Summary
- **Overall Match Score**: **8.2 / 10.0**
  - Academic Fit: 7.0 / 10.0
  - Geography: 9.0 / 10.0
  - Financials: 9.5 / 10.0
- **Topics Identified**: Event Reconstruction, Graph Algorithms, Machine Learning, Particle Flow, CMS, FCC, HL-LHC, C++, Quantum-physics (ArXiv category)
- **Compensation**: Not explicitly stated in description (CERN standard salary applies, typically > 5,000 EUR/month gross)
- **Evaluator Notes**: The vacancy is located in Switzerland, strongly aligning with the candidate's geographic preferences. The role focuses on computational particle physics, specifically event reconstruction using graph algorithms and machine learning for CMS and FCC experiments. While the candidate's primary research interests lean towards theoretical quantum physics and QCD phenomenology, they are open to computational positions, making this a moderate academic fit. CERN offers a highly competitive compensation package that significantly exceeds the candidate's financial minimums. Eligibility is met via Spanish citizenship. Note: The vacancy accepts a Master's or PhD, so the candidate should verify if the position is structured as a formal PhD program rather than a staff scientist role.

---

## Original Vacancy Description

```text
The next generation of experiments, the HL-LHC upgrade of CMS and the Future Circular Collider, needs event reconstruction that is fast, accurate and portable across CPUs and GPUs. Every reconstruction algorithm and every machine-learning model is trained and judged against the simulation truth. Today that truth is stored in static, detector-specific objects. Each object is pre-grouped for one purpose, it cannot be navigated, and it separates calorimeter truth from tracker truth.
CERN has built a prototype that replaces them. It is one navigable, event-level graph of the generator and simulation history, with calorimeter and tracker hit indices on top. Reconstruction code then reasons in terms of stable physics abstractions: particles, vertices, decay branches and hits.
You will make this the truth model of the future. You will generalise the prototype into an experiment-independent library, you will bring it into the FCC software stack, and you will use it to build the next reconstruction: graph algorithms and modern machine learning for clustering, particle flow and particle identification, and reliable matching between reconstructed objects and truth. You will join the EP-FCC group, and you will work on both CMS and FCC-ee.
Your responsibilities:
Generalise the CMS MC-truth graph into a detector-independent and experiment-independent library. Separate the graph data model, the navigation API and the hit index from the experiment data-format bindings.
Develop the bindings. Keep the CMSSW binding working, and add a binding for the FCC stack (Key4hep, EDM4hep, Gaudi), so that both experiments build the same graph from their own simulation output.
Extend the data model. Add multi-surface boundary crossings, sparse association storage, and a reduced hit-index layout. Handle pileup consistently.
Develop the reconstruction-to-truth association. Extend the adaptive branch associator, which selects the truth level that best matches a reconstructed object, and validate it on merged topologies such as converted photons, bremsstrahlung and early hadronic interactions.
Define what is reconstructible. Derive it from the truth graph and the detector description, using cell granularity, energy and time resolution, readout thresholds and two-object separation.
Apply portable graph algorithms and advanced machine learning, for example graph neural networks and transformers, to reconstruction tasks in CMS (HGCAL and TICL) and in FCC detectors: clustering, linking, particle flow and particle identification.
Build the training datasets and the labels from the truth graph. Define the metrics, calibrate the model outputs, and check the model before it feeds reconstruction.
Contribute the code to the official repositories of CMS and of the FCC software stack, with unit tests, documentation and code review.
Present the results in CMS and FCC meetings, in software forums and in publications.
This role includes team supervision responsibilities.
Your profile:
A Master's Degree or a PhD in Physics, Computer Science, Applied Mathematics or a related field.
Demonstrated experience with modern C++ in a large, shared and peer-reviewed codebase, for example CMSSW, Gaudi or Key4hep.
Demonstrated experience with time-aware event reconstruction and detector simulation in a high-energy physics experiment.
Demonstrated experience with heterogeneous and portable computing, for example Alpaka, SYCL, CUDA or HIP.
Experience with Python and with at least one machine-learning framework, preferably PyTorch.
Experience with graph and clustering algorithms.
Experience with git, code review and continuous integration.
Skills:
C++20.
Clustering, event reconstruction.
Detector simulation.
Particle flow.
CMSSW,Key4hep.
Heterogeneous computing.
Spoken and written English, with a commitment to learn French.
Eligibility criteria:
You are a national of a
CERN Member or Associate Member State
.
You have a professional background in Physics (or a related field) and have either:
a
Master's degree with 2 to 6 years
of post-graduation professional experience;
or a
PhD with no more than 3 years
of post-graduation professional experience.
You have never had a CERN fellow or graduate contract before.

Job closing date:
13.11.2026 at 23:59 CET.
Contract duration: 24 months, with a possible extension up to 36 months maximum.
Working hours: 40 hours per week
Job flexibility: Hybrid
Target start date: 01-January-2027
This position involves:
Participation in a regular stand-by duty, including nights, Sundays and official holidays.
Work during nights, Sundays and official holidays.
Shift work.
Given the occupational health risks associated with this position, the selected candidate must obtain medical clearance before a contract offer is confirmed.
Job reference: EP-FCC-2026-166-GRAP
Field of work: Experimental Physics
Benchmark job: 200140 - Applied Physicist
Global Benefits
A monthly net stipend of either 6372 or 7004 Swiss Francs per month depending on your degree.
30 days of paid leave per year plus 2 weeks annual closure.
Coverage by CERN’s comprehensive health insurance scheme (for yourself, your spouse and children), and membership of the CERN Pension Fund.
Family, child and infant monthly allowances depending on your individual circumstances.
A relocation package (installation grant and travel expenses) depending on your individual circumstances.
Possibility to extend your contract up to 36 months.
On-the-job and formal training including language classes.
Overview of CERN - Discover a world where the impossible is made possible!
At CERN, the European Organization for Nuclear Research, we are pushing the frontiers of science and technology. Our groundbreaking work brings together not only physicists but also a diverse range of professionals from engineering, technical, scientific, and administrative fields. Together, we foster an environment where innovation and collaboration thrive.
Every day, we face exciting new challenges and opportunities to contribute to cutting-edge research that shapes our understanding of the universe. We meet these challenges through the diverse perspectives within our teams, ensuring every contribution is valued and driving our shared sense of inclusion and purpose. Diversity is a core value of CERN since its foundation, and it remains central to our mission and continued success.
If you are ready to be part of a dynamic, inclusive community pushing the boundaries of knowledge, CERN is the place where your curiosity and skills can thrive. Be part of our mission to uncover what lies at the heart of the universe!
TAKE PART!
More information about us, here:
careers.cern
```
