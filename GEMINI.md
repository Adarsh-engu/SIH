### CORE SKILL: The Kinetic UI Principle
**Directive:** Never deliver flat, static, or raw-CSS-styled user interfaces. You must leverage high-quality modern component ecosystems, theme providers, and animation frameworks to create fluid, interactive, and professionally designed web applications. 

**Execution Rules:**
1. **Premium Component Ecosystems:** Do not build basic UI elements (buttons, navbars, modals) from scratch using raw CSS. Default to modern, accessible libraries like Shadcn UI, Aceternity UI, Magic UI, or Tailwind UI to scaffold layouts rapidly and professionally.
2. **Framework-Driven Animation:** Never write lengthy raw CSS `@keyframes` or complex vanilla JavaScript event listeners for motion. Use established, declarative animation libraries (e.g., Framer Motion for React, GSAP) to handle micro-interactions, complex visualizers, scroll effects, and page transitions.
3. **Thematic Cohesion:** Always implement a consistent, modern design system. Automatically assume the need for cohesive color palettes, typography scales, proper whitespace, and modern staples (e.g., Dark Mode toggles, glassmorphism, responsive grid layouts). 
4. **Template Scaffolding:** When asked for a new page, dashboard, or layout, retrieve and adapt the structure of high-quality, community-standard templates rather than inventing a layout blindly. Ensure the UI looks "production-ready" immediately.

### CORE SKILL: The Antigravity Principle
**Directive:** Never reinvent the wheel. Before writing custom logic, you must identify and implement the accepted industry-standard package, framework, or standard library. Do not "vibecode" custom, fragile algorithms for solved problems.

**Execution Rules:**
1. **Import Over Implement:** If a well-maintained library exists for a task (e.g., date formatting, state management, complex data structures, authentication), use it. Do not write from-scratch implementations. 
2. **Idiomatic Frameworks:** Strictly adhere to the design patterns of the current stack. (e.g., Do not write vanilla DOM manipulation in React; do not write raw SQL injections when Spring Boot/PostgreSQL ORM is the established standard).
3. **Justify Imports:** When solving a problem, briefly state which standard package you are leveraging and why, followed by the installation command (e.g., `npm install` or `pip install`) and the concise implementation.
4. **Code Golfing:** Prioritize solutions that reduce lines of code and rely on battle-tested ecosystem tools rather than lengthy, AI-generated boilerplate.
