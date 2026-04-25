# PROJECT_CONSTRAINTS.md

Repo-level constraints for `x`.

- `x` is a reusable workflow and local state helper, not a product-specific operating system.
- Product-specific context must be loaded from the target project, not embedded in generic role prompts.
- Runtime state must not be written into product repos by default.
- The default runtime root is `~/.x/projects/<project-key>/`.
- The target project profile path is `.x/project/profile.md`.
- Do not add broad abstraction layers before a second real project requires them.
