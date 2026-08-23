# Contributing

Contributions should make the workflow safer, clearer, or easier to adopt without turning one project's preference into a universal restriction.

## Before changing behavior

1. Describe the concrete failure or adoption problem.
2. Decide whether the fix belongs in the Skill, a conditional reference, a generated template, or a deterministic script.
3. Preserve existing repositories by default; new automation must preview conflicts before writing.
4. Add or update a behavioral test.

Run:

```shell
python -m unittest discover -s tests -v
```

Pull requests should explain the user-visible workflow change, the risk it addresses, how it was verified, and any remaining limitation. Git history details do not need to lead the explanation.
