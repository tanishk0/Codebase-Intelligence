from tree_sitter_language_pack import get_parser


def parse_code(source_code: str, language: str):
    parser = get_parser(language)
    return parser.parse(source_code.encode("utf-8"))


def extract_symbols(tree):
    symbols = []

    def walk(node):
        if node.type in {
            "function_definition",
            "class_definition",
            "function_declaration",
            "class_declaration",
            "method_definition",
        }:
            symbols.append({
                "type": node.type,
                "name": next(
                    (
                        child.text.decode("utf-8")
                        for child in node.children
                        if child.type in {"identifier", "property_identifier"}
                    ),
                    None,
                ),
                "start_line": node.start_point.row + 1,
                "end_line": node.end_point.row + 1,
            })

        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return symbols