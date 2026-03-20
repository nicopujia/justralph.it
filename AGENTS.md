## Documentation

- Anytime you update code, you must make sure to update existing docs correspondingly.
- When you write code, you should document the non-obvious in a concise way.
- Do not use em-dashes for docs.

## Tooling

- Use `uv` for any Python-related task.

Be extremely concise. Sacrifice grammar for the sake of concision.

## Commit Messages

Use conventional commits.
Mostly lowercase.
Abbreviate when obvious (e.g. `deps`, `cfg`, `init`, `impl`, `refactor`, `rm`, `mv`, etc.).
Keep subjects short.
If you include a body, keep it concise.

```
<Examples>
  <Example>
    feat: impl username/password auth

    Closes: ex-001
  </Example>
  <Example>
    docs: update setup instructions in README

    Replace pip with uv.
  </Example>
</Examples>
```
