from jumpscale.loader import j
from textwrap import dedent
from jumpscale.sals.chatflows.chatflows import chatflow_step
from jumpscale.sals.jukebox.jukebox_deploy_chatflow import JukeboxDeployChatflow


class DashDeploy(JukeboxDeployChatflow):
    title = "Dash"
    SOLUTION_TYPE = "dash"
    QUERY = {"cru": 4, "mru": 8, "hru": 100}
    ENTERY_POINT = "/start_dash.sh"
    FLIST = "https://hub.grid.tf/ashraf.3bot/arrajput-dash-flist-1.0.flist"
    steps = [
        "get_deployment_name",
        "block_chain_info",
        "choose_farm",
        "set_expiration",
        "environment",
        "payment",
        "deploy",
        "success",
    ]

    @chatflow_step(title="User configurations")
    def environment(self):
        self.env = {}
        self.rpc_password = j.data.idgenerator.idgenerator.chars(8)
        self.secret_env = {"rpcuser": self.owner_tname, "rpcpasswd": self.rpc_password}
        self.metadata = {
            "form_info": {"chatflow": self.SOLUTION_TYPE, "Solution name": self.deployment_name,},
        }

    @chatflow_step(title="Success", disable_previous=True, final_step=True)
    def success(self):
        message = f"""\
        # You deployed {self.nodes_count} nodes of {self.SOLUTION_TYPE}
        <br />\n
        your RPC credentials: <br />
        username: {self.owner_tname}<br />
        password: {self.rpc_password}<br />
        """
        self.md_show(dedent(message), md=True)


chat = DashDeploy
