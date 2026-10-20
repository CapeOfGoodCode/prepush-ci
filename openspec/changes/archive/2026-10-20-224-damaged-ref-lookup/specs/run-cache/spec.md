## ADDED Requirements

### Requirement: A damaged ref in the clone does not hide a result on the remote
The lookup of a result on `origin` SHALL NOT turn into a miss because a ref in the clone is damaged: a result ref whose file is empty or a ref under `refs/prepush-ci` whose name git refuses. When `origin` holds the result of the key, the lookup SHALL fetch it and the result SHALL be reused as for a clone with healthy refs.

#### Scenario: Another result ref emptied
- **WHEN** a session passed the check on a tree in a push to `origin`, a fresh clone holds an emptied file under `.git/refs/prepush-ci/results/` of another name, and it pushes a commit of that tree with the trailer
- **THEN** the check does not run, the push succeeds and the hook's line contains `origin`, the first twelve characters of the tree and the first twelve characters of the commit that passed

#### Scenario: A ref with a refused name
- **WHEN** a fresh clone holds the ref `refs/prepush-ci/results/bad..name`, `origin` holds the result for the tip, and the tip with the trailer is pushed
- **THEN** the check does not run and the push succeeds

### Requirement: The lookup past a damaged ref SHALL NOT start housekeeping
The fetch of the lookup SHALL NOT run auto-maintenance (`gc --auto`), so that no pruning of history happens while git is told to ignore damaged refs.

#### Scenario: A broken ref holds the only copy of a commit
- **WHEN** a ref under `refs/prepush-ci/results/` with a name git refuses (`bad..name`) holds a commit no other ref holds, git's auto-gc is set to run on every fetch and prune at once, `origin` holds the result for the tip, and the tip with the trailer is pushed
- **THEN** the check does not run, the push succeeds and the commit still exists

### Requirement: A lookup that cannot write the result ref is a miss
A lookup whose fetch cannot write the ref of the key, because the clone's ref of that very name is damaged, or because `refs/prepush-ci` is a regular file, SHALL be a miss and the check SHALL run. The push SHALL NOT be refused for it.

#### Scenario: The damaged ref has the name of the key
- **WHEN** the file of the ref `refs/prepush-ci/results/<tree>-<config>` in a fresh clone is empty, `origin` holds the result for the tip, and the tip with the trailer is pushed
- **THEN** the check runs and the push succeeds

#### Scenario: Cache path is a file
- **WHEN** `refs/prepush-ci` in a fresh clone's git directory is a regular file, `origin` holds the result for the tip, and the tip with the trailer is pushed
- **THEN** the check runs and the push succeeds
