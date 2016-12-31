import os
import copy

import anyconfig

from populus import ASSETS_DIR

from populus.utils.functional import (
    cast_return_to_tuple,
)
from populus.utils.chains import (
    get_default_ipc_path as get_geth_default_ipc_path,
)
from populus.utils.config import (
    get_nested_key,
    set_nested_key,
    pop_nested_key,
    get_empty_config,
    flatten_config_items,
    find_project_config_file_path,
    get_default_project_config_file_path,
    get_ini_config_file_path,
)


class empty(object):
    pass


class Config(object):
    def __init__(self, config=None, default_config_info=None):
        if config is None:
            config = get_empty_config()
        else:
            config = anyconfig.to_container(config)

        if default_config_info is None:
            default_config_info = tuple()
        self.default_config_info = default_config_info
        self.config_for_write = config
        self.config_for_read = apply_default_configs(
            self.config_for_write,
            self.default_config_info,
        )

    def get(self, key, default=None):
        try:
            return get_nested_key(self.config_for_read, key)
        except KeyError:
            return default

    def get_config(self, key, defaults=None):
        try:
            return type(self)(self[key], defaults)
        except KeyError:
            return type(self)(get_empty_config(), defaults)

    def pop(self, key, default=empty):
        try:
            value = pop_nested_key(self.config_for_read, key)
        except KeyError:
            if default is empty:
                raise
            else:
                value = default

        try:
            pop_nested_key(self.config_for_write, key)
        except KeyError:
            pass

        return value

    @cast_return_to_tuple
    def keys(self, flatten=False):
        for key, _ in self.items(flatten=flatten):
            yield key

    @cast_return_to_tuple
    def items(self, flatten=False):
        if flatten:
            _items = flatten_config_items(self.config_for_read)
        else:
            _items = self.config_for_read.items()
        for key, value in _items:
            yield key, value

    def update(self, other, **kwargs):
        if isinstance(other, type(self)):
            other = other.config_for_read
        self.config_for_write.update(copy.deepcopy(other), **kwargs)
        self.config_for_read.update(copy.deepcopy(other), **kwargs)

    def __str__(self):
        return str(self.config_for_read)

    def __repr__(self):
        return repr(self.config_for_read)

    def __eq__(self, other):
        return self.config_for_read == other

    def __bool__(self):
        if self.config_for_write:
            return True
        elif not self.default_config_info:
            return False
        else:
            return any(tuple(zip(*self.default_config_info)[1]))

    def __getitem__(self, key):
        return get_nested_key(self.config_for_read, key)

    def __setitem__(self, key, value):
        set_nested_key(self.config_for_read, key, value)
        return set_nested_key(self.config_for_write, key, value)

    def __contains__(self, key):
        try:
            self[key]
        except KeyError:
            return False
        else:
            return True

    def __copy__(self):
        return type(self)(
            copy.copy(self.config_for_write),
            copy.copy(self.default_config_info),
        )

    def __deepcopy__(self, memo):
        return type(self)(
            copy.deepcopy(self.config_for_write, memo),
            copy.deepcopy(self.default_config_info, memo),
        )


def set_geth_mainnet_ipc_path(config):
    _config = Config(config)
    _config['provider.settings.ipc_path'] = get_geth_default_ipc_path(testnet=False)
    return _config.config_for_write


def set_geth_ropsten_ipc_path(config):
    _config = Config(config)
    _config['provider.settings.ipc_path'] = get_geth_default_ipc_path(testnet=True)
    return _config.config_for_write


POPULUS_CONFIG_DEFAULTS = {
    ('compilation', 'compilation.config.json', anyconfig.MS_DICTS),
    # Mainnet
    ('chains.mainnet.web3', 'chains.mainnet.web3.config.json'),
    # Ropsten
    ('chains.ropsten.web3', 'chains.ropsten.web3.config.json'),
    # TestRPC
    ('chains.testrpc.web3', 'chains.testrpc.web3.config.json'),
    # Tester
    ('chains.tester.web3', 'chains.tester.web3.config.json'),
    # Temp
    ('chains.temp.web3', 'chains.temp.web3.config.json'),
    # Web3 Configs
    ('web3.InfuraRopsten', 'web3.InfuraRopsten.config.json'),
    ('web3.InfuraMainnet', 'web3.InfuraMainnet.config.json'),
    (
        'web3.GethMainnet',
        'web3.GethMainnet.config.json',
        anyconfig.MS_NO_REPLACE,
        set_geth_mainnet_ipc_path,
    ),
    (
        'web3.GethRopsten',
        'web3.GethRopsten.config.json',
        anyconfig.MS_NO_REPLACE,
        set_geth_ropsten_ipc_path,
    ),
    (
        'web3.GethEphemeral',
        'web3.GethEphemeral.config.json',
        anyconfig.MS_NO_REPLACE,
    ),
    ('web3.TestRPC', 'web3.TestRPC.config.json'),
    ('web3.Tester', 'web3.Tester.config.json'),
}


@cast_return_to_tuple
def load_default_config_info(config_defaults=POPULUS_CONFIG_DEFAULTS):
    for config_value in config_defaults:
        if len(config_value) == 2:
            write_path, config_file_name = config_value
            merge_strategy = anyconfig.MS_NO_REPLACE
            callback = None
        elif len(config_value) == 3:
            write_path, config_file_name, merge_strategy = config_value
            callback = None
        elif len(config_value) == 4:
            write_path, config_file_name, merge_strategy, callback = config_value
        else:
            raise ValueError("Invalid Default Configuration")

        config_file_path = os.path.join(ASSETS_DIR, config_file_name)
        loaded_config = anyconfig.load(config_file_path)

        if callback is not None:
            processed_config = callback(loaded_config)
        else:
            processed_config = loaded_config

        yield write_path, processed_config, merge_strategy


def apply_default_configs(config, default_configs):
    merged_config = copy.deepcopy(config)

    for write_path, default_config, merge_strategy in default_configs:
        if write_path not in merged_config:
            set_nested_key(merged_config, write_path, default_config)
        else:
            sub_config = copy.deepcopy(merged_config[write_path])
            sub_config_with_merge_rules = anyconfig.to_container(
                sub_config,
                ac_merge=merge_strategy,
            )
            sub_config_with_merge_rules.update(default_config)

            set_nested_key(merged_config, write_path, sub_config_with_merge_rules)

    return merged_config


def load_config(config_file_path=None):
    if config_file_path is None:
        try:
            config_file_path = find_project_config_file_path()
        except ValueError:
            pass

    if config_file_path:
        project_config = anyconfig.load(config_file_path)
    else:
        project_config = get_empty_config()

    return project_config


def write_config(project_dir, config, write_path=None):
    if write_path is None:
        try:
            write_path = find_project_config_file_path(project_dir)
        except ValueError:
            write_path = get_default_project_config_file_path(project_dir)

    ini_config_file_path = get_ini_config_file_path(project_dir)

    if write_path == ini_config_file_path:
        raise ValueError(
            "The INI configuration format has been deprecated.  Please convert "
            "your configuration file to either `populus.yml` or `populus.json`"
        )

    with open(write_path, 'w') as config_file:
        anyconfig.dump(
            config,
            config_file,
            sort_keys=True,
            indent=2,
            separators=(',', ': '),
        )

    return write_path
