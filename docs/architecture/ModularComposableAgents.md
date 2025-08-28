Modular Composable Agents and coupled with targgeted on-demand tools.


First, a **Planning Agent generated a step-by-step plan** to solve the problem. Each of these steps was **passed to another Planning agent** tasked with breaking down the step into sub-steps that handled the fine-grained details. Then each of these **sub-steps was passed sequentially to an Execution Agent** to carry out the execution. 😄

The over-arching plan was decomposed into 7 phases:

1. environment setup and validating the existence of the data,
2. data pre-processing,
3. fitting of the Gaussian process model,
4. fitting of the Bayesian neural network,
5. assessment of predictive capability,
6. assessment of uncertainty quantification, and
7. summarization and presentation of the results.

