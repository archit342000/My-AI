# Coding standards

1. **Python:** always use the interpreter in `venv/` (`venv/bin/python <script.py>`). Never use the system Python.
2. **Configuration:** all config lives in `backend/config.py`. Never hardcode values.
3. **Database:** always use `db` from `backend.database`. Never write raw SQL outside the database layer.
4. **Logging:** use `log_event()` from `backend.logging`, not `print()`.
5. **Frontend:** no frameworks; plain ES6+ modules (`static/js/`); CSS Custom Properties only.
6. **Errors:** do not mask failures with empty `try/except` blocks or by returning `None` or empty lists.
   Handle errors explicitly or let them propagate so they can be debugged.
7. **Edits:** prefer small, incremental edits over rewriting whole files. Do not replace more code than the change needs.
8. **Libraries:** confirm the current version of a library or tool from its official docs before using it.
9. **Docker:** never modify existing containers. Build temporary ones with unique names.
10. **Tool-call loops:** if repeated tool calls keep failing, change approach (different search terms,
    a different tool, a different way of exploring) instead of repeating them.
