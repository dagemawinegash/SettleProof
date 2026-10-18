# Local setup

SettleProof needs a River inference key, CreateOS EU Sandbox access, and Postgres. Stripe Projects manages the credentials; the app loads them from its generated `.env` file.

In your authenticated Stripe Projects project, check the existing resources first:

```sh
stripe projects status
stripe projects catalog Neon --json
```

If you need a new metadata database, provision the free plan and database. Skip resources that already exist; use the CLI's existing-resource linking flow when available.

```sh
stripe projects add Neon/free --name metadata-plan --accept-tos --yes
stripe projects add Neon/postgres --name run-metadata --accept-tos --yes
```

Store the API keys through the secure prompts, then pull the configuration:

```sh
stripe projects variables set river-api-key --env-key RIVER_API_KEY
stripe projects variables set createos-api-key --env-key CREATEOS_API_KEY
stripe projects env --pull
```

Do not hand-edit CLI-managed `.projects/` files or commit credentials.

| Configuration | Purpose |
| --- | --- |
| `RIVER_API_KEY` | Generate reconciliation programs |
| `CREATEOS_API_KEY` | Execute programs in CreateOS EU sandboxes |
| `RUN_METADATA_CONNECTION_STRING` or `DATABASE_URL` | Store run metadata in Postgres |
| `RIVER_MODEL` | Optional model override; defaults to `zai-org/GLM-5.3-Flash` |

After installing the app, `python -m settleproof doctor` checks model access, CreateOS identity, and database access. This diagnostic writes a small metadata record. Start the browser with `python -m settleproof serve`; use `--port 8001` if port 8000 is occupied.
