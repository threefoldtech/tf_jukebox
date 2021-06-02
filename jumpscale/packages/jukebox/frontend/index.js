Vue.use(Vuex)
Vue.use(Vuetify)

Vue.prototype.$api = apiClient

const vuetify = new Vuetify({
    icons: {
        iconfont: 'mdi'
    },
    theme: {
        themes: {
            light: {
                primary: '#1B4F72',
                secondary: '#CCCBCA',
                accent: '#59B88C',
                success: "#17A589",
                error: '#EC7063',
            },
        },
    }
})
const markdownViewer = httpVueLoader('./components/MarkdownViewer.vue')

const baseComponent = httpVueLoader('./components/base/Component.vue')
const baseDialog = httpVueLoader('./components/base/Dialog.vue')
const baseSection = httpVueLoader('./components/base/Section.vue')
const external = httpVueLoader('./components/base/External.vue')
const popup = httpVueLoader('./components/base/Popup.vue')
const code = httpVueLoader('./components/base/Code.vue')

const app = httpVueLoader('./App.vue')
const home = httpVueLoader('./components/solutions/Solution.vue')
// const solutionChatflow = httpVueLoader('./components/solutions/SolutionChatflow.vue')
// const workloads = httpVueLoader('./components/solutions/Workloads.vue')
const license = httpVueLoader('./components/License.vue')
const terms = httpVueLoader('./components/Terms.vue')
const disclaimer = httpVueLoader('./components/Disclaimer.vue')


const marketplaceHome = httpVueLoader('./components/marketplace/Home.vue')
const solution = httpVueLoader('./components/marketplace/Solution.vue')
const solutionChatflow = httpVueLoader('./components/marketplace/SolutionChatflow.vue')

Vue.mixin({
    methods: {
        alert(message, status) {
            this.$root.$emit('popup', message, status)
        }
    }
})

Vue.component("base-component", baseComponent)
Vue.component("base-section", baseSection)
Vue.component("base-dialog", baseDialog)
Vue.component("external", external)
Vue.component("popup", popup)
Vue.component("code-area", code)
Vue.component("markdown-view", markdownViewer)

const router = new VueRouter({
    routes: [
        { name: "Home", path: '/', component: home, props: true, meta: { icon: "mdi-apps" } },
        { name: "License", path: '/license', component: license, meta: { icon: "mdi-apps" } },
        { name: "Terms", path: '/terms', component: terms, meta: { icon: "mdi-apps" } },
        { name: "Disclaimer", path: '/disclaimer', component: disclaimer, meta: { icon: "mdi-apps" } },
        // { name: "SolutionChatflow", path: '/chats/:topic/:vdc_name', component: solutionChatflow, props: true, meta: { icon: "mdi-tune" } },
        // { name: "Workloads", path: '/workloads', component: workloads, meta: { icon: "mdi-tune" }, },
        
        { name: "Marketplace", path: '/marketplace', component: marketplaceHome, meta: { icon: "mdi-tune" } },
        { name: "Solution", path: '/:type', component: solution, props: true, meta: { icon: "mdi-apps" } },
        { name: "SolutionChatflow", path: '/solutions/:topic', component: solutionChatflow, props: true, meta: { icon: "mdi-tune" } },


    ]
})

// router.beforeEach((to, from, next) => {
//     const AllowedEndPoint = "api/allowed";
//     axios.get(AllowedEndPoint).then(results => {
//         let agreed = results.data.allowed;
//         if (to.name !== "License" && !agreed) {
//             next("/license");
//         }
//     })
//     next();
// })


const getUser = async() => {
    return axios.get("/auth/authenticated/").then(res => true).catch(() => false)
}

router.beforeEach(async(to, from, next) => {
    to.params.loggedin = await getUser()
    const AllowedEndPoint = "api/allowed";
    axios.get(AllowedEndPoint).then(results => {
        let agreed = results.data.allowed;
        if (to.name !== "License" && !agreed) {
            next("/license");
        }
    }).catch((e) => {
        if (to.name === "SolutionChatflow") {
            let nextUrl = encodeURIComponent(`/vdc_dashboard/#${to.path}`)
            window.location.href = `/auth/login?next_url=${nextUrl}`
        } else {
            next();
        }
    })
    next();
})

Vue.use(VueCodemirror)

new Vue({
    el: '#app',
    components: { App: app },
    router,
    vuetify
})
