import argparse
import collections
import json
import logging
import os
import subprocess
import sys
import time

from .python import Python
from .javascript import Javascript
from .ruby import Ruby
from .php import PHP
from .model import (TRUNK_COLOR, LEAF_COLOR, NODE_COLOR, GROUP_TYPE, OWNER_CONST,
                    Edge, Group, Node, Variable, is_installed, flatten)

VERSION = '2.5.1'

IMAGE_EXTENSIONS = ('png', 'svg')
TEXT_EXTENSIONS = ('dot', 'gv', 'json')
VALID_EXTENSIONS = IMAGE_EXTENSIONS + TEXT_EXTENSIONS

DESCRIPTION = "Generate flow charts from your source code. " \
              "See the README at https://github.com/scottrogowski/code2flow."

LEGEND = """subgraph legend{
    rank = min;
    label = "legend";
    Legend [shape=none, margin=0, label = <
        <table cellspacing="0" cellpadding="0" border="1"><tr><td>Code2flow Legend</td></tr><tr><td>
        <table cellspacing="0">
        <tr><td>Regular function</td><td width="50px" bgcolor='%s'></td></tr>
        <tr><td>Trunk function (nothing calls this)</td><td bgcolor='%s'></td></tr>
        <tr><td>Leaf function (this calls nothing else)</td><td bgcolor='%s'></td></tr>
        <tr><td>Function call</td><td><font color='black'>&#8594;</font></td></tr>
        </table></td></tr></table>
        >];
}""" % (NODE_COLOR, TRUNK_COLOR, LEAF_COLOR)

LANGUAGES = {
    'py': Python,
    'js': Javascript,
    'mjs': Javascript,
    'rb': Ruby,
    'php': PHP,
}


class LanguageParams():
    """
    Shallow structure to make storing language-specific parameters cleaner
    """

    def __init__(self, source_type='script', ruby_version='27'):
        self.source_type = source_type
        self.ruby_version = ruby_version


class SubsetParams():
    """
    Shallow structure to make storing subset-specific parameters cleaner.
    """

    def __init__(self, target_function, upstream_depth, downstream_depth):
        self.target_function = target_function
        self.upstream_depth = upstream_depth
        self.downstream_depth = downstream_depth

    @staticmethod
    def generate(target_function, upstream_depth, downstream_depth):
        """
        :param target_function str:
        :param upstream_depth int:
        :param downstream_depth int:
        :rtype: SubsetParams|Nonetype
        """
        if upstream_depth and not target_function:
            raise AssertionError("--upstream-depth requires --target-function")

        if downstream_depth and not target_function:
            raise AssertionError("--downstream-depth requires --target-function")

        if not target_function:
            return None

        if not (upstream_depth or downstream_depth):
            raise AssertionError("--target-function requires --upstream-depth or --downstream-depth")

        if upstream_depth < 0:
            raise AssertionError("--upstream-depth must be >= 0. Exclude argument for complete depth.")

        if downstream_depth < 0:
            raise AssertionError("--downstream-depth must be >= 0. Exclude argument for complete depth.")

        return SubsetParams(target_function, upstream_depth, downstream_depth)


def _find_target_node(subset_params, all_nodes):
    """
    Find the node referenced by subset_params.target_function
    :param subset_params SubsetParams:
    :param all_nodes list[Node]:
    :rtype: Node
    """
    target_nodes = []
    for node in all_nodes:
        if node.token == subset_params.target_function or \
                node.token_with_ownership() == subset_params.target_function or \
                node.name() == subset_params.target_function:
            target_nodes.append(node)
    if not target_nodes:
        raise AssertionError("Could not find node %r to build a subset." % subset_params.target_function)
    if len(target_nodes) > 1:
        raise AssertionError("Found multiple nodes for %r: %r. Try either a `class.func` or "
                             "`filename::class.func`." % (subset_params.target_function, target_nodes))
    return target_nodes[0]


def _filter_nodes_for_subset(subset_params, all_nodes, edges):
    """
    Given subset_params, return a set of all nodes upstream and downstream of the target node.
    :param subset_params SubsetParams:
    :param all_nodes list[Node]:
    :param edges list[Edge]:
    :rtype: set[Node]
    """
    target_node = _find_target_node(subset_params, all_nodes)
    downstream_dict = collections.defaultdict(set)
    upstream_dict = collections.defaultdict(set)
    for edge in edges:
        upstream_dict[edge.node1].add(edge.node0)
        downstream_dict[edge.node0].add(edge.node1)

    include_nodes = {target_node}
    step_nodes = {target_node}
    next_step_nodes = set()

    for _ in range(subset_params.downstream_depth):
        for node in step_nodes:
            next_step_nodes.update(downstream_dict[node])
        include_nodes.update(next_step_nodes)
        step_nodes = next_step_nodes
        next_step_nodes = set()

    step_nodes = {target_node}
    next_step_nodes = set()

    for _ in range(subset_params.upstream_depth):
        for node in step_nodes:
            next_step_nodes.update(upstream_dict[node])
        include_nodes.update(next_step_nodes)
        step_nodes = next_step_nodes
        next_step_nodes = set()

    return include_nodes


def _filter_edges_for_subset(new_nodes, edges):
    """
    Given the subset of nodes, filter for edges within this subset
    :param new_nodes set[Node]:
    :param edges list[Edge]:
    :rtype: list[Edge]
    """
    new_edges = []
    for edge in edges:
        if edge.node0 in new_nodes and edge.node1 in new_nodes:
            new_edges.append(edge)
    return new_edges


def _filter_groups_for_subset(new_nodes, file_groups):
    """
    Given the subset of nodes, do housekeeping and filter out for groups within this subset
    :param new_nodes set[Node]:
    :param file_groups list[Group]:
    :rtype: list[Group]
    """
    for file_group in file_groups:
        for node in file_group.all_nodes():
            if node not in new_nodes:
                node.remove_from_parent()

    new_file_groups = [g for g in file_groups if g.all_nodes()]

    for file_group in new_file_groups:
        for group in file_group.all_groups():
            if not group.all_nodes():
                group.remove_from_parent()

    return new_file_groups


def _filter_for_subset(subset_params, all_nodes, edges, file_groups):
    """
    Given subset_params, return the subset of nodes, edges, and groups
    upstream and downstream of the target node.
    :param subset_params SubsetParams:
    :param all_nodes list[Node]:
    :param edges list[Edge]:
    :param file_groups list[Group]:
    :rtype: list[Group], list[Node], list[Edge]
    """
    new_nodes = _filter_nodes_for_subset(subset_params, all_nodes, edges)
    new_edges = _filter_edges_for_subset(new_nodes, edges)
    new_file_groups = _filter_groups_for_subset(new_nodes, file_groups)
    return new_file_groups, list(new_nodes), new_edges


def generate_json(nodes, edges):
    '''
    Generate a json string from nodes and edges
    See https://github.com/jsongraph/json-graph-specification

    :param nodes list[Node]: functions
    :param edges list[Edge]: function calls
    :rtype: str
    '''
    nodes = [n.to_dict() for n in nodes]
    nodes = {n['uid']: n for n in nodes}
    edges = [e.to_dict() for e in edges]

    return json.dumps({"graph": {
        "directed": True,
        "nodes": nodes,
        "edges": edges,
    }})


def write_file(outfile, nodes, edges, groups, hide_legend=False,
               no_grouping=False, as_json=False):
    '''
    Write a dot file that can be read by graphviz

    :param outfile File:
    :param nodes list[Node]: functions
    :param edges list[Edge]: function calls
    :param groups list[Group]: classes and files
    :param hide_legend bool:
    :rtype: None
    '''

    if as_json:
        content = generate_json(nodes, edges)
        outfile.write(content)
        return

    splines = "polyline" if len(edges) >= 500 else "ortho"

    content = "digraph G {\n"
    content += "concentrate=true;\n"
    content += f'splines="{splines}";\n'
    content += 'rankdir="LR";\n'
    if not hide_legend:
        content += LEGEND
    for node in nodes:
        content += node.to_dot() + ';\n'
    for edge in edges:
        content += edge.to_dot() + ';\n'
    if not no_grouping:
        for group in groups:
            content += group.to_dot()
    content += '}\n'
    outfile.write(content)


def determine_language(individual_files):
    """
    Given a list of filepaths, determine the language from the first
    valid extension

    :param list[str] individual_files:
    :rtype: str
    """
    for source, _ in individual_files:
        suffix = source.rsplit('.', 1)[-1]
        if suffix in LANGUAGES:
            logging.info("Implicitly detected language as %r.", suffix)
            return suffix
    raise AssertionError(f"Language could not be detected from input {individual_files}. ",
                         "Try explicitly passing the language flag.")


def get_sources_and_language(raw_source_paths, language):
    """
    Given a list of files and directories, return just files.
    If we are not passed a language, determine it.
    Filter out files that are not of that language

    :param list[str] raw_source_paths: file or directory paths
    :param str|None language: Input language
    :rtype: (list, str)
    """

    individual_files = []
    for source in sorted(raw_source_paths):
        if os.path.isfile(source):
            individual_files.append((source, True))
            continue
        for root, _, files in os.walk(source):
            for f in files:
                individual_files.append((os.path.join(root, f), False))

    if not individual_files:
        raise AssertionError("No source files found from %r" % raw_source_paths)
    logging.info("Found %d files from sources argument.", len(individual_files))

    if not language:
        language = determine_language(individual_files)

    sources = set()
    for source, explicity_added in individual_files:
        if explicity_added or source.endswith('.' + language):
            sources.add(source)
        else:
            logging.info("Skipping %r which is not a %s file. "
                         "If this is incorrect, include it explicitly.",
                         source, language)

    if not sources:
        raise AssertionError("Could not find any source files given {raw_source_paths} "
                             "and language {language}.")

    sources = sorted(list(sources))
    logging.info("Processing %d source file(s)." % (len(sources)))
    for source in sources:
        logging.info("  " + source)

    return sources, language


def make_file_group(tree, filename, extension):
    """
    Given an AST for the entire file, generate a file group complete with
    subgroups, nodes, etc.

    :param tree ast:
    :param filename str:
    :param extension str:

    :rtype: Group
    """
    language = LANGUAGES[extension]

    subgroup_trees, node_trees, body_trees = language.separate_namespaces(tree)
    group_type = GROUP_TYPE.FILE
    token = os.path.split(filename)[-1].rsplit('.' + extension, 1)[0]
    line_number = 0
    display_name = 'File'
    import_tokens = language.file_import_tokens(filename)

    file_group = Group(token, group_type, display_name, import_tokens,
                       line_number, parent=None)
    for node_tree in node_trees:
        for new_node in language.make_nodes(node_tree, parent=file_group, filename=filename):
            file_group.add_node(new_node)

    file_group.add_node(language.make_root_node(body_trees, parent=file_group), is_root=True)

    for subgroup_tree in subgroup_trees:
        file_group.add_subgroup(language.make_class_group(subgroup_tree, parent=file_group))
    return file_group


def _find_link_for_call(call, node_a, all_nodes):
    """
    Given a call that happened on a node (node_a), return the node
    that the call links to and the call itself if >1 node matched.

    :param call Call:
    :param node_a Node:
    :param all_nodes list[Node]:

    :returns: The node it links to and the call if >1 node matched.
    :rtype: (Node|None, Call|None)
    """

    all_vars = node_a.get_variables(call.line_number)

    for var in all_vars:
        var_match = call.matches_variable(var)
        if var_match:
            # Unknown modules (e.g. third party) we don't want to match)
            if var_match == OWNER_CONST.UNKNOWN_MODULE:
                return None, None
            assert isinstance(var_match, Node)
            return var_match, None

    possible_nodes = []
    if call.is_attr():
        for node in all_nodes:
            # checking node.parent != node_a.file_group() prevents self linkage in cases like
            # function a() {b = Obj(); b.a()}
            if call.token == node.token and node.parent != node_a.file_group():
                possible_nodes.append(node)
    else:
        for node in all_nodes:
            if call.token == node.token \
                    and isinstance(node.parent, Group) \
                    and node.parent.group_type == GROUP_TYPE.FILE:
                possible_nodes.append(node)
            elif call.token == node.parent.token and node.is_constructor:
                possible_nodes.append(node)

    if len(possible_nodes) == 1:
        return possible_nodes[0], None
    if len(possible_nodes) > 1:
        return None, call
    return None, None


def _find_links(node_a, all_nodes):
    """
    Iterate through the calls on node_a to find everything the node links to.
    This will return a list of tuples of nodes and calls that were ambiguous.

    :param Node node_a:
    :param list[Node] all_nodes:
    :param BaseLanguage language:
    :rtype: list[(Node, Call)]
    """

    links = []
    for call in node_a.calls:
        lfc = _find_link_for_call(call, node_a, all_nodes)
        assert not isinstance(lfc, Group)
        links.append(lfc)
    return list(filter(None, links))


def map_it(sources, extension, no_trimming, exclude_namespaces, exclude_functions, include_only_namespaces,
           include_only_functions, skip_parse_errors, lang_params, exclude_lib_files=False):
    '''
    Given a language implementation and a list of filenames, do these things:
    1. Read/parse source ASTs
    2. Find all groups (classes/modules) and nodes (functions) (a lot happens here)
    3. Trim namespaces / functions that we don't want
    4. Consolidate groups / nodes given all we know so far
    5. Attempt to resolve the variables (point them to a node or group)
    6. Find all calls between all nodes
    7. Loudly complain about duplicate edges that were skipped
    8. Trim nodes that didn't connect to anything

    :param list[str] sources:
    :param str extension:
    :param bool no_trimming:
    :param list exclude_namespaces:
    :param list exclude_functions:
    :param list include_only_namespaces:
    :param list include_only_functions:
    :param bool skip_parse_errors:
    :param LanguageParams lang_params:
    :param bool exclude_lib_files:

    :rtype: (list[Group], list[Node], list[Edge])
    '''

    language = LANGUAGES[extension]

    # 0. Assert dependencies
    language.assert_dependencies()

    # 1. Read/parse source ASTs
    file_ast_trees = []
    for source in sources:
        try:
            if exclude_lib_files and language.is_library_file(source, lang_params):
                logging.debug("Skipping lib file %s", source)
                continue
            else:
                file_ast_trees.append((source, language.get_tree(source, lang_params)))
        except Exception as ex:
            if skip_parse_errors:
                logging.warning("Could not parse %r. (%r) Skipping...", source, ex)
            else:
                raise ex

    # 2. Find all groups (classes/modules) and nodes (functions) (a lot happens here)
    file_groups = []
    for source, file_ast_tree in file_ast_trees:
        file_group = make_file_group(file_ast_tree, source, extension)
        file_groups.append(file_group)

    # 3. Trim namespaces / functions to exactly what we want
    if exclude_namespaces or include_only_namespaces:
        file_groups = _limit_namespaces(file_groups, exclude_namespaces, include_only_namespaces)
    if exclude_functions or include_only_functions:
        file_groups = _limit_functions(file_groups, exclude_functions, include_only_functions)

    # 4. Consolidate structures
    all_subgroups = flatten(g.all_groups() for g in file_groups)
    all_nodes = flatten(g.all_nodes() for g in file_groups)

    nodes_by_subgroup_token = collections.defaultdict(list)
    for subgroup in all_subgroups:
        if subgroup.token in nodes_by_subgroup_token:
            logging.warning("Duplicate group name %r. Naming collision possible.",
                            subgroup.token)
        nodes_by_subgroup_token[subgroup.token] += subgroup.nodes

    for group in file_groups:
        for subgroup in group.all_groups():
            subgroup.inherits = [nodes_by_subgroup_token.get(g) for g in subgroup.inherits]
            subgroup.inherits = list(filter(None, subgroup.inherits))
            for inherit_nodes in subgroup.inherits:
                for node in subgroup.nodes:
                    node.variables += [Variable(n.token, n, n.line_number) for n in inherit_nodes]

    # 5. Attempt to resolve the variables (point them to a node or group)
    for node in all_nodes:
        node.resolve_variables(file_groups)

    # Not a step. Just log what we know so far
    logging.info("Found groups %r." % [g.label() for g in all_subgroups])
    logging.info("Found nodes %r." % sorted(n.token_with_ownership() for n in all_nodes))
    logging.info("Found calls %r." % sorted(list(set(c.to_string() for c in
                                                     flatten(n.calls for n in all_nodes)))))
    logging.info("Found variables %r." % sorted(list(set(v.to_string() for v in
                                                         flatten(n.variables for n in all_nodes)))))

    # 6. Find all calls between all nodes
    bad_calls = []
    edges = []
    for node_a in list(all_nodes):
        links = _find_links(node_a, all_nodes)
        for node_b, bad_call in links:
            if bad_call:
                bad_calls.append(bad_call)
            if not node_b:
                continue
            edges.append(Edge(node_a, node_b))

    # 7. Loudly complain about duplicate edges that were skipped
    bad_calls_strings = set()
    for bad_call in bad_calls:
        bad_calls_strings.add(bad_call.to_string())
    bad_calls_strings = list(sorted(list(bad_calls_strings)))
    if bad_calls_strings:
        logging.info("Skipped processing these calls because the algorithm "
                     "linked them to multiple function definitions: %r." % bad_calls_strings)

    if no_trimming:
        return file_groups, all_nodes, edges

    # 8. Trim nodes that didn't connect to anything
    nodes_with_edges = set()
    for edge in edges:
        nodes_with_edges.add(edge.node0)
        nodes_with_edges.add(edge.node1)

    for node in all_nodes:
        if node not in nodes_with_edges:
            node.remove_from_parent()

    for file_group in file_groups:
        for group in file_group.all_groups():
            if not group.all_nodes():
                group.remove_from_parent()

    file_groups = [g for g in file_groups if g.all_nodes()]
    all_nodes = list(nodes_with_edges)

    if not all_nodes:
        logging.warning("No functions found! Most likely, your file(s) do not have "
                        "functions that call each other. Note that to generate a flowchart, "
                        "you need to have both the function calls and the function "
                        "definitions. Or, you might be excluding too many "
                        "with --exclude-* / --include-* / --target-function arguments. ")
        logging.warning("Code2flow will generate an empty output file.")

    return file_groups, all_nodes, edges


def _limit_namespaces(file_groups, exclude_namespaces, include_only_namespaces):
    """
    Exclude namespaces (classes/modules) which match any of the exclude_namespaces

    :param list[Group] file_groups:
    :param list exclude_namespaces:
    :param list include_only_namespaces:
    :rtype: list[Group]
    """

    removed_namespaces = set()

    for group in list(file_groups):
        if group.token in exclude_namespaces:
            for node in group.all_nodes():
                node.remove_from_parent()
            removed_namespaces.add(group.token)
        if include_only_namespaces and group.token not in include_only_namespaces:
            for node in group.nodes:
                node.remove_from_parent()
            removed_namespaces.add(group.token)

        for subgroup in group.all_groups():
            print(subgroup, subgroup.all_parents())
            if subgroup.token in exclude_namespaces:
                for node in subgroup.all_nodes():
                    node.remove_from_parent()
                removed_namespaces.add(subgroup.token)
            if include_only_namespaces and \
                    subgroup.token not in include_only_namespaces and \
                    all(p.token not in include_only_namespaces for p in subgroup.all_parents()):
                for node in subgroup.nodes:
                    node.remove_from_parent()
                removed_namespaces.add(group.token)

    for namespace in exclude_namespaces:
        if namespace not in removed_namespaces:
            logging.warning(f"Could not exclude namespace '{namespace}' "
                            "because it was not found.")
    return file_groups


def _limit_functions(file_groups, exclude_functions, include_only_functions):
    """
    Exclude nodes (functions) which match any of the exclude_functions

    :param list[Group] file_groups:
    :param list exclude_functions:
    :param list include_only_functions:
    :rtype: list[Group]
    """

    removed_functions = set()

    for group in list(file_groups):
        for node in group.all_nodes():
            if node.token in exclude_functions or \
                    (include_only_functions and node.token not in include_only_functions):
                node.remove_from_parent()
                removed_functions.add(node.token)

    for function_name in exclude_functions:
        if function_name not in removed_functions:
            logging.warning(f"Could not exclude function '{function_name}' "
                            "because it was not found.")
    return file_groups


def _generate_graphviz(output_file, extension, final_img_filename):
    """
    Write the graphviz file
    :param str output_file:
    :param str extension:
    :param str final_img_filename:
    """
    start_time = time.time()
    logging.info("Running graphviz to make the image...")
    command = ["dot", "-T" + extension, output_file]
    with open(final_img_filename, 'w') as f:
        try:
            subprocess.run(command, stdout=f, check=True)
            logging.info("Graphviz finished in %.2f seconds." % (time.time() - start_time))
        except subprocess.CalledProcessError:
            logging.warning("*** Graphviz returned non-zero exit code! "
                            "Try running %r for more detail ***", ' '.join(command + ['-v', '-O']))


def _generate_final_img(output_file, extension, final_img_filename, num_edges):
    """
    Write the graphviz file
    :param str output_file:
    :param str extension:
    :param str final_img_filename:
    :param int num_edges:
    """
    _generate_graphviz(output_file, extension, final_img_filename)
    logging.info("Completed your flowchart! To see it, open %r.",
                 final_img_filename)


def code2flow(raw_source_paths, output_file, language=None, hide_legend=True, exclude_namespaces=None,
              exclude_functions=None, include_only_namespaces=None, include_only_functions=None, no_grouping=False,
              no_trimming=False, skip_parse_errors=False, lang_params=None, subset_params=None, level=logging.INFO,
              exclude_lib_files=False):
    """
    Top-level function. Generate a diagram based on source code.
    Can generate either a dotfile or an image.

    :param list[str] raw_source_paths: file or directory paths
    :param str|file output_file: path to the output file. SVG/PNG will generate an image.
    :param str language: input language extension
    :param bool hide_legend: Omit the legend from the output
    :param list exclude_namespaces: List of namespaces to exclude
    :param list exclude_functions: List of functions to exclude
    :param list include_only_namespaces: List of namespaces to include
    :param list include_only_functions: List of functions to include
    :param bool no_grouping: Don't group functions into namespaces in the final output
    :param bool no_trimming: Don't trim orphaned functions / namespaces
    :param bool skip_parse_errors: If a language parser fails to parse a file, skip it
    :param lang_params LanguageParams: Object to store lang-specific params
    :param subset_params SubsetParams: Object to store subset-specific params
    :param int level: logging level
    :param bool exclude_lib_files: If True, files in libs and 3rd party code is ignored
    :rtype: None
    """
    start_time = time.time()

    if not isinstance(raw_source_paths, list):
        raw_source_paths = [raw_source_paths]
    lang_params = lang_params or LanguageParams()

    exclude_namespaces = exclude_namespaces or []
    assert isinstance(exclude_namespaces, list)
    exclude_functions = exclude_functions or []
    assert isinstance(exclude_functions, list)
    include_only_namespaces = include_only_namespaces or []
    assert isinstance(include_only_namespaces, list)
    include_only_functions = include_only_functions or []
    assert isinstance(include_only_functions, list)

    logging.basicConfig(format="Code2Flow: %(message)s", level=level)

    sources, language = get_sources_and_language(raw_source_paths, language)

    output_ext = None
    if isinstance(output_file, str):
        assert '.' in output_file, "Output filename must end in one of: %r." % set(VALID_EXTENSIONS)
        output_ext = output_file.rsplit('.', 1)[1] or ''
        assert output_ext in VALID_EXTENSIONS, "Output filename must end in one of: %r." % \
                                               set(VALID_EXTENSIONS)

    final_img_filename = None
    if output_ext and output_ext in IMAGE_EXTENSIONS:
        if not is_installed('dot') and not is_installed('dot.exe'):
            raise AssertionError(
                "Can't generate a flowchart image because neither `dot` nor "
                "`dot.exe` was found. Either install graphviz (see the README) "
                "or, if you just want an intermediate text file, set your --output "
                "file to use a supported text extension: %r" % set(TEXT_EXTENSIONS))
        final_img_filename = output_file
        output_file, extension = output_file.rsplit('.', 1)
        output_file += '.gv'

    file_groups, all_nodes, edges = map_it(sources, language, no_trimming, exclude_namespaces, exclude_functions,
                                           include_only_namespaces, include_only_functions, skip_parse_errors,
                                           lang_params, exclude_lib_files)

    if subset_params:
        logging.info("Filtering into subset...")
        file_groups, all_nodes, edges = _filter_for_subset(subset_params, all_nodes, edges, file_groups)

    file_groups.sort()
    all_nodes.sort()
    edges.sort()

    logging.info("Generating output file...")

    if isinstance(output_file, str):
        with open(output_file, 'w') as fh:
            as_json = output_ext == 'json'
            write_file(fh, nodes=all_nodes, edges=edges,
                       groups=file_groups, hide_legend=hide_legend,
                       no_grouping=no_grouping, as_json=as_json)
    else:
        write_file(output_file, nodes=all_nodes, edges=edges,
                   groups=file_groups, hide_legend=hide_legend,
                   no_grouping=no_grouping)

    logging.info("Wrote output file %r with %d nodes and %d edges.",
                 output_file, len(all_nodes), len(edges))
    if not output_ext == 'json':
        logging.info("For better machine readability, you can also try outputting in a json format.")
    logging.info("Code2flow finished processing in %.2f seconds." % (time.time() - start_time))

    # translate to an image if that was requested
    if final_img_filename:
        _generate_final_img(output_file, extension, final_img_filename, len(edges))


def main(sys_argv=None):
    """
    CLI interface. Sys_argv is a parameter for the sake of unittest coverage.
    :param sys_argv list:
    :rtype: None
    """
    parser = argparse.ArgumentParser(
        description=DESCRIPTION,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'sources', metavar='sources', nargs='+',
        help='source code file/directory paths.')
    parser.add_argument(
        '--output', '-o', default='out.png',
        help=f'output file path. Supported types are {VALID_EXTENSIONS}.')
    parser.add_argument(
        '--language', choices=['py', 'js', 'rb', 'php'],
        help='process this language and ignore all other files.'
             'If omitted, use the suffix of the first source file.')
    parser.add_argument(
        '--target-function',
        help='output a subset of the graph centered on this function. '
             'Valid formats include `func`, `class.func`, and `file::class.func`. '
             'Requires --upstream-depth and/or --downstream-depth. ')
    parser.add_argument(
        '--upstream-depth', type=int, default=0,
        help='include n nodes upstream of --target-function.')
    parser.add_argument(
        '--downstream-depth', type=int, default=0,
        help='include n nodes downstream of --target-function.')
    parser.add_argument(
        '--exclude-functions',
        help='exclude functions from the output. Comma delimited.')
    parser.add_argument(
        '--exclude-namespaces',
        help='exclude namespaces (Classes, modules, etc) from the output. Comma delimited.')
    parser.add_argument(
        '--include-only-functions',
        help='include only functions in the output. Comma delimited.')
    parser.add_argument(
        '--include-only-namespaces',
        help='include only namespaces (Classes, modules, etc) in the output. Comma delimited.')
    parser.add_argument(
        '--no-grouping', action='store_true',
        help='instead of grouping functions into namespaces, let functions float.')
    parser.add_argument(
        '--no-trimming', action='store_true',
        help='show all functions/namespaces whether or not they connect to anything.')
    parser.add_argument(
        '--hide-legend', action='store_true',
        help='by default, Code2flow generates a small legend. This flag hides it.')
    parser.add_argument(
        '--skip-parse-errors', action='store_true',
        help='skip files that the language parser fails on.')
    parser.add_argument(
        '--skip-lib-files', action='store_true',
        help='skip files that are not part of user code and is coming from 3rd party libraries.')
    parser.add_argument(
        '--source-type', choices=['script', 'module'], default='script',
        help='js only. Parse the source as scripts (commonJS) or modules (es6)')
    parser.add_argument(
        '--ruby-version', default='27',
        help='ruby only. Which ruby version to parse? This is passed directly into ruby-parse. '
             'Use numbers like 25, 27, or 31.')
    parser.add_argument(
        '--quiet', '-q', action='store_true',
        help='suppress most logging')
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='add more logging')
    parser.add_argument(
        '--version', action='version', version='%(prog)s ' + VERSION)

    sys_argv = sys_argv or sys.argv[1:]
    args = parser.parse_args(sys_argv)
    level = logging.INFO
    if args.verbose and args.quiet:
        raise AssertionError("Passed both --verbose and --quiet flags")
    if args.verbose:
        level = logging.DEBUG
    if args.quiet:
        level = logging.WARNING

    exclude_namespaces = list(filter(None, (args.exclude_namespaces or "").split(',')))
    exclude_functions = list(filter(None, (args.exclude_functions or "").split(',')))
    include_only_namespaces = list(filter(None, (args.include_only_namespaces or "").split(',')))
    include_only_functions = list(filter(None, (args.include_only_functions or "").split(',')))

    lang_params = LanguageParams(args.source_type, args.ruby_version)
    subset_params = SubsetParams.generate(args.target_function, args.upstream_depth,
                                          args.downstream_depth)

    code2flow(raw_source_paths=args.sources, output_file=args.output, language=args.language,
              hide_legend=args.hide_legend, exclude_namespaces=exclude_namespaces, exclude_functions=exclude_functions,
              include_only_namespaces=include_only_namespaces, include_only_functions=include_only_functions,
              no_grouping=args.no_grouping, no_trimming=args.no_trimming, skip_parse_errors=args.skip_parse_errors,
              lang_params=lang_params, subset_params=subset_params, level=level, exclude_lib_files=args.skip_lib_files)
