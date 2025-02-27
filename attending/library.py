import importlib
import pkg_resources
from pathlib import Path

from types import ModuleType

from .downloader import write_to_file
from .doc import Module
from .fallback import get_doc_url
from .index import load_attending_index, load_index

MONITOR_ERROR = """'{0}' needs both __doc_url__  and __version__ defined. It has
{0}.__doc_url__ = {1}
{0}.__version__ = {2}
"""


def get_module_version(module):
    if hasattr(module, "__version__"):
        return module.__version__
    try:
        # Couldn't get __version__ from module
        # We can either:
        # Use pkg_resources to get it
        name = module if isinstance(module, str) else module.__name__
        return pkg_resources.working_set.by_key[name].version
    except KeyError:
        # Assume it's the latest from PyPI
        return "latest"


def can_monitor(module):
    return hasattr(module, "__doc_url__")


def cannot_monitor(module):
    msg = MONITOR_ERROR.format(module.__name__,
                               getattr(module, "__doc_url__", None),
                               get_module_version(module))

    return ValueError(msg)


def options_exhausted(module):
    return RuntimeError(f"Failed not find fallback url for {module}")


class Library:
    def __init__(self, home=Path().home()):
        self.location = home / Path(".attending")
        if not self.location.exists():
            self.location.mkdir(parents=True)

    def fetch(self, name, version, url):
        if not self.in_collection(name, version):
            self._add_project(name, version, url)
        return self.get_edition(name, version)

    def _add_project(self, name, version, url):
        destination = self.location / name / version
        if destination.exists():
            raise FileExistsError(f"{destination}")
        destination.mkdir(parents=True)
        write_to_file(self.location, name, version, url)

    def retire(self, name, version):
        self.get_edition(name, version).retire()

    def in_collection(self, name, version):
        module_dir = self.location / name
        if not module_dir.is_dir():
            return False
        return (module_dir / version).is_dir()

    def get_edition(self, name, version):
        if not self.in_collection(name, version):
            raise KeyError
        return Module(self.location, name)[version]


def attending_doc(module, version=None, home=Path().home()):
    if version is None:
        version = get_module_version(module)
    lib = Library(home=home)
    if isinstance(module, ModuleType):
        return lib.get_edition(module.__name__, version)
    else:
        return lib.get_edition(module, version)


def fetch(module, version=None, home=Path().home()):
    """
    A convenience top-level function for fetching docs

    Parameters
    ----------
    module : string or module
        The module whose docs we want to pull up
    version: string, optional
        The version for `module`, will fall-back to latest, if not specified.
    """
    if isinstance(module, ModuleType):
        return fetch_via_module(module, version, home=home)
    else:
        return fetch_via_name(module, version, home=home)


def fetch_via_module(module, version=None, home=Path().home()):
    """
    Fetch the docs for a given imported module

    Parameters
    ----------
    module : module
        The module whose docs we want to pull up
    version: string, optional
        The version for `module`, will fall-back to current, if not specified.
    """
    lib = Library(home=home)
    mod_name = module.__name__

    if version is None:
        version = get_module_version(module)

    if hasattr(module, "__doc_url__"):
        __doc_url__ = module.__doc_url__
        lib.fetch(mod_name, version, __doc_url__)
    else:
        # try our fall back
        url = get_doc_url(mod_name)
        write_to_file(lib.location, mod_name, version, url)

    return lib.get_edition(mod_name, version)


def fetch_via_name(module, version=None, url=None, home=Path().home()):
    """
    Fetch the docs for a given imported module

    Parameters
    ----------
    module : string
        The module whose docs we want to pull up
    version: string, optional
        The version for `module`, will fall-back to current, if not specified.
    url: string, optional
        The location to retrieve the docs from, defaults to what the package specifies
    """
    lib = Library(home=home)
    if version is None:
        version = get_module_version(module)

    if url is None:
        # url was not given to us so we must assume that it is already installed and use that
        try:
            python_module = importlib.import_module(module)
        except ImportError:
            url = get_doc_url(module)
            if url is None:
                raise options_exhausted(module, version)
        else:
            return fetch_via_module(python_module, version)
    return lib.fetch(module, version, url)


def fetch_via_local_index(module, home=Path().home()):
    index = load_attending_index()
    local_index_file = Path().home() / ".attending" / "index.csv"
    if local_index_file.exists():
        index.update(load_index(local_index_file))
    if module in index:
        fetch_via_name(module, url=index[module], home=home)
