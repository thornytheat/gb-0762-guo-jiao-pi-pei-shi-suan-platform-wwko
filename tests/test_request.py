def test_non_object_not_treated_as_material(client):
    reply = client.post('/api/assay', json=[])
    assert reply.status_code == 400 and reply.json['code'] == 'JSON_REQUIRED'


def test_formula_and_optimizer_can_be_used_independently(client):
    formula = client.post('/api/formula', json={'sample':'dirty', 'proposal':-1})
    blend = client.post('/api/blend', json={'sample':'dirty', 'proposal':-1})
    assert formula.status_code == 422 and blend.json['allocation'] == {'PJ-01':5000, 'PJ-02':5000}
