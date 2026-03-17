import logging
import shutil
import time

import bd
import psutil

from .agent import Agent
from .config import Config, get_config
from .git_utils import cleanup_branch, ensure_on_main
from .hooks import Hooks
from .init import init_ralph_dir, load_hooks
from .state import State

logger = logging.getLogger(__name__)


def main():
    cfg = get_config()

    init_ralph_dir(cfg)

    log_fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(log_fmt)
    main_log_file_handler = logging.FileHandler(filename=cfg.log_file)
    main_log_file_handler.setFormatter(log_fmt)
    logging.basicConfig(
        handlers=[stdout_handler, main_log_file_handler], level=logging.INFO
    )

    loop_state = State(cfg.state_file)
    hooks = load_hooks(cfg)

    while True:
        restart = _run_loop(cfg, hooks, loop_state, log_fmt)
        if not restart:
            break
        logger.info("Restarting loop")


def _run_loop(
    cfg: Config, hooks: Hooks, loop_state: State, log_fmt: logging.Formatter
) -> bool:
    """Run the main loop. Return True if a restart was requested."""
    i = loop_state.check_crash_recovery(bd_timeout=cfg.bd_timeout)

    logger.info("Calling pre-loop hook")
    hooks.pre_loop(cfg)

    if cfg.max_iters:
        logger.info("Starting the loop")
    else:
        logger.warning("Skipping entire loop: max_iters is 0")
    consecutive_failures = 0
    restart = False

    while True and cfg.max_iters:
        if cfg.stop_file.exists():
            reason = cfg.stop_file.read_text() or "found empty stop file"
            cfg.stop_file.unlink()
            logging.warning("Stopping loop: %s", reason)
            break

        if cfg.restart_file.exists():
            reason = cfg.restart_file.read_text() or "found empty restart file"
            cfg.restart_file.unlink()
            logger.info("Restart requested: %s", reason)
            restart = True
            break

        logger.info("Checking machine resources")
        cpu = round(psutil.cpu_percent(), 2)
        ram = round(psutil.virtual_memory().percent, 2)
        total_disk, used_disk, _ = shutil.disk_usage("/")
        disk = round(used_disk / total_disk * 100, 2)
        logger.info("CPU: %s%% | RAM: %s%% | Disk: %s%%", cpu, ram, disk)
        if (
            disk > cfg.vm_res_threshold
            or ram > cfg.vm_res_threshold
            or cpu > cfg.vm_res_threshold
        ):
            logger.warning(
                "Stopping loop: machine resources usage over %s%% threshold",
                cfg.vm_res_threshold,
            )
            break
        else:
            logger.info("Machine resources usage is OK")

        logger.info("Getting next ready issue")
        issue = bd.get_next_ready_issue(timeout=cfg.bd_timeout)

        if not issue:
            logger.info("No ready issues currently. Waiting for new ones")
            try:
                issue = bd.wait_for_next_ready_issue(
                    cfg.poll_interval,
                    stop_file=cfg.stop_file,
                    restart_file=cfg.restart_file,
                    timeout=cfg.bd_timeout,
                )
            except bd.StopRequested as e:
                logger.warning("Stopping loop while waiting for issues: %s", e)
                break
            except bd.RestartRequested as e:
                logger.info("Restart requested while waiting for issues: %s", e)
                restart = True
                break

        logger.info("Retrieved issue: %r", issue)

        logger.info("Getting extra args & kwargs")
        extra_args, extra_kwargs = hooks.extra_args_kwargs(cfg, issue)

        logger.info(
            "Creating instance with args %s and kwargs %s", extra_args, extra_kwargs
        )
        ralph = Agent(
            issue=issue,
            model=cfg.model,
            prompt_file=cfg.prompt_file,
            i=i,
            *extra_args,
            **extra_kwargs,
        )

        ralph.start_issue(timeout=cfg.bd_timeout)

        logger.info("Preparing git state for issue %s", issue.id)
        ensure_on_main()
        cleanup_branch(issue.id)

        iter_log_file = cfg.logs_dir / f"iteration_{i}.log"
        iter_handler = logging.FileHandler(filename=iter_log_file)
        iter_handler.setFormatter(log_fmt)
        logging.getLogger().addHandler(iter_handler)

        logger.info("Calling pre-iteration hook")
        hooks.pre_iter(cfg, issue, i)

        loop_state.save(issue.id, i)

        iter_error: Exception | None = None
        try:
            logger.info("Starting Ralph")
            for stdout in ralph.run(timeout=cfg.subprocess_timeout):
                logger.info("[Ralph] %s", stdout.rstrip())
            logger.info("Ralph concluded working: %s", ralph.status)
            consecutive_failures = 0
        except Exception as exc:
            iter_error = exc
            consecutive_failures += 1
            logger.exception(
                "Failed unexpectedly (consecutive failures: %s)",
                consecutive_failures,
            )
            if cfg.max_retries >= 0 and consecutive_failures > cfg.max_retries:
                cfg.stop_file.write_text(
                    f"exceeded max retries ({cfg.max_retries}) "
                    f"after {consecutive_failures} consecutive failures"
                )
                logger.error("Max retries exceeded; will stop on next iteration")
            else:
                backoff = min(2**consecutive_failures, 300)
                logger.info("Backing off for %ss before retrying", backoff)
                time.sleep(backoff)
        finally:
            logger.info("Calling post-iteration hook")
            hooks.post_iter(cfg, issue, i, ralph.status, iter_error)

            i += 1
            loop_state.clear()
            iter_handler.close()
            logging.getLogger().removeHandler(iter_handler)

            if cfg.max_iters >= 0 and i >= cfg.max_iters:
                logger.warning(
                    "Stopping loop: reached max iterations (%s)", cfg.max_iters
                )
                break

    logger.info("Finished loop. Calling post-loop hook")
    hooks.post_loop(cfg, i)

    return restart


if __name__ == "__main__":
    main()
