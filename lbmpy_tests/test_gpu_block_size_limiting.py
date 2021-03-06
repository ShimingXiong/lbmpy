from lbmpy.creationfunctions import create_lb_ast


def test_gpu_block_size_limiting():
    too_large = 2048*2048
    opt = {'target': 'gpu', 'gpu_indexing_params': {'block_size': (too_large, too_large, too_large)}}
    ast = create_lb_ast(stencil='D3Q19', cumulant=True, relaxation_rate=1.8, optimization=opt,
                        compressible=True, force_model='guo')
    limited_block_size = ast.indexing.call_parameters((1024, 1024, 1024))
    kernel = ast.compile()
    assert all(b < too_large for b in limited_block_size['block'])
    bs = [too_large, too_large, too_large]
    ast.indexing.limit_block_size_by_register_restriction(bs, kernel.num_regs)
    assert all(b < too_large for b in bs)
