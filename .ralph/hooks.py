"""Ralph lifecycle hooks.

Override methods to customise behaviour.
Run `python -c "from ralph.hooks import Hooks; help(Hooks)"` to see the full interface.
"""

from ralph.hooks import Hooks


class CustomHooks(Hooks):
    def pre_loop(self, cfg):
        pass

    def pre_iter(self, cfg, issue, iteration):
        pass

    def post_iter(self, cfg, issue, iteration, status, error):
        pass

    def post_loop(self, cfg, iterations_completed):
        pass

    def extra_args_kwargs(self, cfg, issue):
        return (), {}
