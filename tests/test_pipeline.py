def test_evidence_matches_preview_inventory_and_formula(client):
    stock = client.post('/api/stock', json={'sample':'dirty'}).json
    key = client.post('/api/batches', json={'sample':'dirty'}).json['batch_id']
    pack = client.get('/api/export/' + key).json
    assert pack['record']['stages']['stock'] == stock
    assert pack['record']['stages']['blend']['allocation'] == {'PJ-01':5000, 'PJ-02':5000}
