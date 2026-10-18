"""Keep owned Windows services from surviving a terminated launcher."""

import os


class ProcessGroup:
    def __init__(self):
        self.handle = None
        if os.name == "nt":
            import win32job

            self.handle = win32job.CreateJobObject(None, "")
            limits = win32job.QueryInformationJobObject(
                self.handle, win32job.JobObjectExtendedLimitInformation
            )
            limits["BasicLimitInformation"]["LimitFlags"] |= (
                win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )
            win32job.SetInformationJobObject(
                self.handle, win32job.JobObjectExtendedLimitInformation, limits
            )

    def add(self, process):
        if self.handle is None or process.poll() is not None:
            return
        import win32job

        try:
            # Popen owns this exact native handle; never reopen a guessed PID.
            win32job.AssignProcessToJobObject(self.handle, int(process._handle))
            # Windows venv launchers may already have started the real Python
            # child before Popen returns. Attach that existing owned tree too;
            # children created afterward inherit their parent's job membership.
            import psutil
            import win32api

            parent = psutil.Process(process.pid)
            for _ in range(2):
                for child in parent.children(recursive=True):
                    handle = None
                    try:
                        handle = win32api.OpenProcess(
                            0x0100 | 0x0001 | 0x1000, False, child.pid
                        )
                        # psutil checks creation time, so a recycled PID cannot
                        # grant this launcher ownership of an unrelated process.
                        if child.is_running() and not win32job.IsProcessInJob(
                            handle, self.handle
                        ):
                            win32job.AssignProcessToJobObject(self.handle, handle)
                    except Exception:
                        if child.is_running():
                            raise
                    finally:
                        if handle is not None:
                            handle.Close()
        except Exception:
            if process.poll() is None:
                raise RuntimeError(
                    "Windows could not attach a local service to Derek's process group. Stop this runtime and review the desktop dependencies before restarting."
                ) from None

    def close(self):
        if self.handle is not None:
            self.handle.Close()
            self.handle = None
