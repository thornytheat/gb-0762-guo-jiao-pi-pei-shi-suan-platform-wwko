from app.stages import STAGES


def test_station_links_and_stock_page(client):
    home = client.get('/')
    assert '配方余量轨'.encode() in home.data and b'17000 g' in home.data
    for path, name in STAGES:
        reply = client.get('/trial/' + path)
        assert reply.status_code == 200 and name.encode() in reply.data


def test_invalid_form_retains_repair_fields(client):
    response = client.post('/trial/formula', data={'sample':'custom','proposal':'{broken','assays':'draft,row','step_g':'350'})
    assert all(value in response.data for value in (b'BAD_PROPOSAL_JSON', b'{broken', b'draft,row', b'350'))
