# Local database

`migrations/0001_initial.sql` creates the V0 source-of-truth schema. It is mounted into the local PostgreSQL container only when the database volume is first created.

Production migrations must use a dedicated migration runner, explicit backups, and the expand/migrate/contract process. Do not rely on container initialization scripts in production.

