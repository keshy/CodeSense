---
![Version 2.5.1](https://img.shields.io/badge/version-2.5.1-brightgreen) ![Build passing](https://img.shields.io/badge/build-passing-brightgreen) ![Coverage 100%](https://img.shields.io/badge/coverage-100%25-brightgreen)

---

# CodeSense: Deep Code Insight Through Dynamic Call Flows

**CodeSense** is an intuitive and powerful analysis tool designed to give you unparalleled insight into your codebase. Whether you're working with **Python, JavaScript, PHP, or Ruby**, CodeSense goes beyond static analysis by generating dynamic **call flows** that map out how your code truly executes.

Our core approach is built on a robust algorithm:

1.  **Parse Source Files:** We translate your source files into Abstract Syntax Trees (ASTs).
2.  **Identify Definitions:** All function and and method definitions are precisely located.
3.  **Map Calls:** We determine where these functions and methods are called throughout your project.
4.  **Connect the Flow:** Finally, we connect the dots, creating a comprehensive call graph that visualizes the execution flow.
5.  **Leverage GenAI for flow and method summaries:** We use genAI to enable users to search and analyze the code in the way they want. 

---

### Why CodeSense? Understand Your Code, Your Way.

CodeSense empowers diverse users to understand complex codebases from their unique perspectives:

* **For Security Professionals:** Quickly identify potential vulnerabilities and pinpoint the **most risky code flows** within your application. Understand attack paths and prioritize your security efforts with clear, visual representations of execution.
* **For Developers:** Grasp the full impact of code changes. Before you even touch a line, CodeSense can show you what a modification to a **core method** means for the rest of your system, preventing unforeseen side effects and streamlining your development process.
* **For Architects & Team Leads:** Gain a high-level understanding of system architecture and dependencies. Visualize how different components interact and make informed decisions about refactoring, optimizing, or scaling your applications.
* **For Onboarding New Team Members:** Accelerate the learning curve for new developers by providing them with an instant visual map of the project's structure and execution logic.

CodeSense provides a *highly accurate estimate* of your project's structure. While no algorithm can generate a perfect call graph for dynamic or duck-typed languages due to runtime ambiguities, CodeSense uses sophisticated heuristics to deliver actionable insights. See the "Known Limitations" section for more details.

---

*(Below: CodeSense generating a call flow for a complex project, illustrating its clarity and depth of analysis)*

![CodeSense Output Example](https://raw.githubusercontent.com/scottrogowski/code2flow/master/assets/code2flow_output.png)