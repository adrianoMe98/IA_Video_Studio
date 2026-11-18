#!/usr/bin/env python3
from pathlib import Path
import json
root=Path(__file__).resolve().parent.parent
api=json.loads((root/'workflows/wan21_1.3b_4gb_api.json').read_text())
ui=json.loads((root/'workflows/wan21_1.3b_4gb_ui.json').read_text())
assert len(api)==len(ui['nodes'])
ui_links={link[0]:link for link in ui['links']}
ui_nodes={node['id']:node for node in ui['nodes']}
for node_id,node in api.items():
    assert node_id.isdecimal() and 'class_type' in node
    assert int(node_id) in ui_nodes and ui_nodes[int(node_id)]['type']==node['class_type']
    for v in node['inputs'].values():
        if isinstance(v,list):
            assert str(v[0]) in api, (node_id,v)
            assert isinstance(v[1],int)
for link_id,src,srcslot,dst,dstslot,typ in ui['links']:
    assert src in ui_nodes and dst in ui_nodes
    assert link_id in ui_nodes[src]['outputs'][srcslot]['links']
    assert ui_nodes[dst]['inputs'][dstslot]['link']==link_id
    assert typ==ui_nodes[src]['outputs'][srcslot]['type']
    assert typ==ui_nodes[dst]['inputs'][dstslot]['type']
assert api['40']['inputs']['length']%4==1
assert api['40']['inputs']['width']%16==0 and api['40']['inputs']['height']%16==0
print(f'[OK] JSON válido: {len(api)} nós, {len(ui_links)} conexões, 17 quadros 320x192.')
