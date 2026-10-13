# CMO v0.1.4 task-local test execution audit

Status: ROUTE ACCEPTED for fixed offline Python unittest command only. This is not a release verdict.

Reviewed source: scratch/owned_test_job.py SHA256 aa3cf9a052c0d49aca70d759a79458aff438c2930a14c278ad3838686bdd7bd0; scratch/probe_owned_test_job.py SHA256 6ccbdc086f0f0a834ed2a16ca73fb7dd1254cd7a5c309e392060c9e61a476d5d.

The route is scoped to WIP/Comics Meta Organizer-v014. Git Bash launches the fixed command /c/Python314/python.exe -B -m unittest discover -s tests. Fixture writes and logs go under scratch/owned-test-job; no live app, accounts, data, port, or deployment operations are authorized.

Mechanism: native Windows Job with KILL_ON_JOB_CLOSE, unnamed noninheritable handle, no breakaway flags, atomic STARTUPINFOEX JOB_LIST at CreateProcess, suspended child membership verification before resume. Parent process handle is opened once before spawn. Startup-inclusive monotonic deadline is 600000ms. Root exit, errors, timeout, parent death, or supervisor death close/terminate the Job and descendants. API failures fail closed.

Foreground ownership: suite requires a fresh 32-hex nonce and atomic lease JSON counter. Explicit foreground calls renew the counter at most every 20 seconds; no background automatic renewals. Supervisor measures time since changed counter using its own monotonic clock. Without renewal it closes the Job after 30 seconds plus polling/scheduling tolerance. Tool cancellation is therefore bounded cleanup, not immediate cleanup. Host process persistence alone is not treated as caller lifetime.

Evidence: scratch/owned-test-job/containment-probes.json. Seven modes passed in Ender's measured 17.3 seconds: normal exit, shortened deadline (exit124), actual rejected attribute API (WinError50, exit125 before child), missing executable (WinError2, exit125), shortened lease expiration (exit125), abrupt supervisor termination, and exact disposable parent exit. Child/grandchild process HANDLEs were opened before termination and verified signaled; no foreign process-tree kill. Probe controller uses bounded waits and disposable helper with self-expiration20s. Outer controller invocation has hard execFile timeout600000ms.

Limit: parent-mode log contains leading NUL bytes because supervisor and fixture redirect shared parent.log. Held-handle containment observations are independent of that logging defect. This route does not certify test correctness, grant generic infrastructure deployment, or clear a release. Changes to reviewed runner hashes require another audit. Preserve source and JSON evidence through handoff.

Primary mechanism references: [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects), [Microsoft atomic process Job assignment](https://devblogs.microsoft.com/oldnewthing/20230209-00/?p=107812/), [UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute).
