"""One entry point for the existing hypothetical teaching experiments."""
from flask import Response, abort, render_template, request

GROUPS = (
    {'id':'exposure','title':'Exposure and compartments','description':'Follow amounts through mathematical transit stages.',
     'experiments':(
         {'endpoint':'transit_example','title':'Transit compartments','question':'How does an input move through a delayed absorption model?',
          'output':'Concentration, amounts and mass balance','scope':'Invented parameters; compartments are not organs.'},
         {'endpoint':'transit_regimen_example','title':'Repeated inputs','question':'How do repeated additions change a generic concentration curve?',
          'output':'Single versus repeated inputs','scope':'Fixed teaching schedule; no treatment recommendation.'})},
    {'id':'binding','title':'Target binding','description':'Compare equilibrium with the time needed to approach it.',
     'experiments':(
         {'endpoint':'target_occupancy_demo','title':'Equilibrium occupancy','question':'How does free concentration relate to equilibrium binding?',
          'output':'Bound fraction at equilibrium','scope':'Hypothetical affinity; no clinical effect calculation.'},
         {'endpoint':'binding_kinetics_demo','title':'Binding kinetics','question':'Can equal affinity hide different binding speeds?',
          'output':'Time-dependent binding','scope':'Invented association and dissociation rates.'},
         {'endpoint':'binding_pulse_demo','title':'Binding after a pulse','question':'What happens to binding when free concentration switches off?',
          'output':'Association and dissociation over time','scope':'An imposed site concentration pulse, not patient PK.'})},
    {'id':'turnover','title':'Production and loss','description':'Explore how a downstream quantity depletes and recovers.',
     'experiments':(
         {'endpoint':'protein_turnover_demo','title':'Turnover fundamentals','question':'How does turnover speed change depletion and recovery?',
          'output':'Relative amount in two invented systems','scope':'Unspecified protein; no assay calibration.'},
         {'endpoint':'turnover_experiment','title':'Production versus loss','question':'Can the same equilibrium arise from different mechanisms?',
          'output':'Adjustable production/loss comparison','scope':'Hypothetical process changes; no drug-specific mechanism.'})},
    {'id':'connected','title':'Connected experiments','description':'Explore an explicit, hypothetical connection between modules.',
     'experiments':(
         {'endpoint':'binding_turnover_experiment','title':'Binding drives turnover','question':'How does persistent binding affect an assumed downstream process?',
          'output':'Binding and downstream amount','scope':'Invented one-way occupancy-to-loss rule.'},
         {'endpoint':'site_exposure_experiment','title':'Exposure → binding → turnover','question':'How do different time scales shape the connected response?',
          'output':'Prescribed concentration, binding and downstream amount','scope':'Hypothetical site exposure; separate from saved patient PK.'})},
)
ENDPOINTS = frozenset('landscape.'+row['endpoint'] for group in GROUPS for row in group['experiments']) | {'landscape.simulation_lab', 'landscape.bortezomib_proteasome_demo', 'landscape.bortezomib_evidence_review', 'landscape.bortezomib_figure_review', 'landscape.bortezomib_timecourse', 'landscape.bortezomib_assumptions'}


def register_simulation_lab_pages(bp):
    @bp.context_processor
    def simulation_navigation():
        return {'simulation_endpoints':ENDPOINTS}

    @bp.get('/simulation-lab')
    def simulation_lab():
        if request.args:abort(400)
        return Response(render_template('landscape_simulation_lab.html',groups=GROUPS),headers={
            'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
