# Design

## Decisions

- **A scenario added to an existing requirement, not a requirement of its own.** The rule that text handed to git is converted exactly is already pinned by "The tool's text is UTF-8, whatever the locale" and "The locale decides only the operating system's strings" (#154). A second requirement would state it twice. The case the hook has, a config value as a subprocess argument, belongs with the requirement that already names the hooks and non-ASCII arguments.
- **Only the trailer gets a scenario.** Standard input and paths handed to git are not scenarios here: `strip` (`hash-object --stdin`) already keeps a non-ASCII trailer under the ASCII locale on `main`, and the message path git gives the hook is relative and ASCII, so a scenario for either would never fail.
- **The requirement text is copied in full** because a modified requirement replaces the old one when the change is archived.
